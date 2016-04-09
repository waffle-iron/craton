"""Models inventory, as defined using SQLAlchemy ORM

Note that our assumption is that we have three independent aspects of
a play:

* specific workflow
* configuration, as managed by a GitHub-like versioned set of config
  files
* inventory for a given tenant, as modeled here

In particular, this means that the configuration is used to interpret
any inventory data.

"""

from oslo_db.sqlalchemy import models
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, Table, Text,
    UniqueConstraint)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, object_mapper, relationship 
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy_utils import Timestamp
from sqlalchemy_utils.types.encrypted import EncryptedType
from sqlalchemy_utils.types.ip_address import IPAddressType
from sqlalchemy_utils.types.json import JSONType
from sqlalchemy_utils.types.url import URLType
from sqlalchemy_utils.types.uuid import UUIDType


# FIXME set up table args for a given database/storage engine, as configured.
# See https://github.com/rackerlabs/craton/issues/19


# Implementation is from the example code in
# http://docs.sqlalchemy.org/en/latest/_modules/examples/vertical/dictlike.html
# also see related support in HostVariable, Host
class ProxiedDictMixin(object):
    """Adds obj[key] access to a mapped class.

    This class basically proxies dictionary access to an attribute
    called ``_proxied``.  The class which inherits this class
    should have an attribute called ``_proxied`` which points to a dictionary.
    """

    def __len__(self):
        return len(self._proxied)

    def __iter__(self):
        return iter(self._proxied)

    def __getitem__(self, key):
        return self._proxied[key]

    def __contains__(self, key):
        return key in self._proxied

    def __setitem__(self, key, value):
        self._proxied[key] = value

    def __delitem__(self, key):
        del self._proxied[key]


class CratonBase(models.ModelBase, Timestamp):
    def __repr__(self):
        mapper = object_mapper(self)
        cols = getattr(self, '_repr_columns',  mapper.primary_key)
        items = [(p.key, getattr(self, p.key))
                 for p in [
                     mapper.get_property_by_column(c) for c in cols]]
        return "{0}({1})".format(
            self.__class__.__name__,
            ', '.join(['{0}={1!r}'.format(*item) for item in items]))


Base = declarative_base(cls=CratonBase)


class Tenant(Base):
    """Supports multitenancy for all other schema elements."""
    __tablename__ = 'tenants'
    id = Column(UUIDType, primary_key=True)
    name = Column(String(255))
    # TODO we will surely need to define more columns, but this
    # suffices to define multitenancy for MVP

    hosts = relationship('Host', back_populates='tenant')
    access_secrets = relationship('AccessSecret', back_populates='tenant')


# FIXME there are stricter requirements for key names in Ansible (see
# http://docs.ansible.com/ansible/playbooks_variables.html#what-makes-a-valid-variable-name),
# and it is not clear what the encoding requirements are for values.
# We may want to represent these requirements with subclassing on
# HostVariables.

class HostVariables(Base):
    """Represents specific key/value bindings for a given host."""
    __tablename__ = 'host_variables'
    host_id = Column(ForeignKey('hosts.id'), primary_key=True)
    key = Column(String(255), primary_key=True)
    value = Column(JSONType)
    _repr_columns = [key, value]


host_tagging = Table(
    'host_tagging', Base.metadata,
    Column('host_id', ForeignKey('hosts.id'), primary_key=True),
    Column('tag_name', ForeignKey('tags.name'), primary_key=True))
                      

# TODO consider using SqlAlchemy's support for inheritance
# hierarchies, eg ComputeHost < Host but first need to determine what
# is uniquely required for a ComputeHost; otherwise use an enumerated
# type to distinguish
#
# see http://docs.sqlalchemy.org/en/latest/orm/inheritance.html#single-table-inheritance

class Host(ProxiedDictMixin, Base):
    """Models descriptive data about a host"""
    __tablename__ = 'hosts'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        UUIDType, ForeignKey('tenants.id'), index=True, nullable=False)
    access_secret_id = Column(Integer, ForeignKey('access_secrets.id'))
    hostname = Column(String(255), nullable=False)
    ip_address = Column(IPAddressType, nullable=False)
    # active hosts for administration; this is not state:
    # the host may or may not be reachable by Ansible/other tooling
    active = Column(Boolean, default=True)

    UniqueConstraint(tenant_id, hostname)
    UniqueConstraint(tenant_id, ip_address)

    _repr_columns=[id, hostname]

    tags = relationship(
        'Tag',
        secondary=host_tagging,
        back_populates='hosts')

    # many-to-one relationship with tenants
    tenant = relationship('Tenant', back_populates='hosts')

    # optional many-to-one relationship with a host-specific secret;
    access_secret = relationship('AccessSecret', back_populates='hosts')

    # provide arbitrary K/V mapping to associated HostVariables table
    variables = relationship(
        'HostVariables',
        collection_class=attribute_mapped_collection('key'))

    # allows access to host variables using dict ops - get/set/del -
    # by using standard Python [] indexing
    _proxied = association_proxy(
        'variables', 'value',
        creator=lambda key, value: HostVariables(key=key, value=value))

    @classmethod
    def with_characteristic(self, key, value):
        return self.variables.any(key=key, value=value)


class Tag(Base):
    """Models a tag on hosts.

    Such tags include groupings like Ansible groups and OpenStack
    regions and cells; as well as arbitrary other tags.

    Rather than subclassing tags, we can use prefixes such as group-
    or region- or cell-.

    It is assumed that hierarchies for groups, if any, is represented
    in an external format, such as a group-of-group inventory in
    Ansible.
    """
    __tablename__ = 'tags'
    name = Column(String(255), primary_key=True)

    _repr_columns = [name]

    # many-to-many relationship with hosts
    hosts = relationship(
        'Host',
        secondary=host_tagging,
        back_populates='tags')


class AccessSecret(Base):
    """Represents a secret for accessing a host. It may be shared.

    For now we assume a PEM-encoded certificate that wraps the private
    key. Such certs may or may not be encrypted; if encrypted, the
    configuration specifies how to interact with other systems, such
    as Barbican or Hashicorp Vault, to retrieve secret data to unlock
    this cert.

    Note that this does not include secrets such as Ansible vault
    files; those are stored outside the inventory database as part of
    the configuration.
    """
    __tablename__ = 'access_secrets'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        UUIDType, ForeignKey('tenants.id'), index=True, nullable=False)
    cert = Column(Text)

    hosts = relationship('Host', back_populates='access_secret')
    tenant = relationship('Tenant', back_populates='access_secrets')
