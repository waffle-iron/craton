===============================
craton
===============================

Fleet management for OpenStack.

* Free software: Apache license
* Documentation: http://github.com/rackerlabs/craton (TODO)
* Source: https://github.com/rackerlabs/craton
* Bugs: http://bugs.launchpad.net/craton


Craton development plan
=======================

Minimum viable Craton
=====================

Goals
-----

This is what we should build, as defined by `Eric Ries
<http://www.startuplessonslearned.com/2009/08/minimum-viable-product-guide.html>`_:

    [T]he minimum viable product is that version of a new product
    which allows a team to collect the maximum amount of validated
    learning about customers with the least effort.


Goals - end-to-end, with Ansible target; but deepen inventory


User stories for MVP
--------------------

FIXME

Inventory
---------

Craton extends the dynamic inventory approach taken by Ansible and
used by OSAD. Craton itself provides an inventory backed by a
database, using SQLAlchemy to model:

FIXME schema diagram

FIXME schema elements description

However, much like Ansible proper can consume a dynamic inventory
script, the inventory API itself is designed to be completely
separable from its database representation.


Use by MVP
~~~~~~~~~~

For the MVP, this separation is explicit and provides something
immediately testable: the REST API will provide a complete set of
inventory artifacts directly runnable by the ``ansible-playbook``
command. First, take an inventory snapshot of the database:

.. code:: bash

  $ curl {endpoint}/v1/inventory/{group}.tgz | tar xz  # FIXME check sulo's REST API

Arbitrary groups can be specified as part of the query performing the
snapshot; also Craton's inventory resolves any external references to
repos for group configration data.

Once unpacked, this tgz has the following directory structure::

  .
  ├── ansible.cfg
  └── hosts
      ├── group_vars
      └── hosts_vars

`ansible.cfg` contains at least this key ``inventory = ./hosts`` (we
may need to use an absolute path, TBD, with some minor rekeying
complexity on the downloading side).

Now run 

.. code:: bash

  $ ansible-playbook my-playbook.yml

FIXME activity diagram showing this flow

FIXME diagram illustrating


Inventory imports
~~~~~~~~~~~~~~~~~


Plays: reliable DevOps for the cloud
------------------------------------

or plays for the similar idea in Ansible.
We might dub these "shifts", as in tectonic shifts; 

Defining a deployment - inventory (a set of hosts (from a group
query)) + a specific workflow (running playbooks, with additional
logic)

This is part of an overall lifecycle


Process flow for MVP
--------------------

- Manage inventory schema, along with corresponding YAML files from
  GitHub customer repos for config, PEM files/blobs.
- Generate inventory file for Ansible, either for TaskFlow to drive
  overall; or for Ansible
- Run playbooks with respect to inventory
- Ansible callbacks for reachability, other errors

We expect these additional elements to be part of the MVP:

- TaskFlow notification to Redis
- Web view on progress, updated with changes ("cloud progress bar")

FIXME activity diagram


Future plans
============

Add support for encrypted Ansible vault files, along with secret retrieval using Barbican or Hashicorp Vault.


Choreography
------------

Choreography, with respect to webhooks

Events
~~~~~~

See for example: GitHub events representing merge to master; PR (for simulation)


Scheduling
~~~~~~~~~~

Following classic product scheduling, we can look at following
constraints to be satisfied/optimized:

- Resource constraints. What hosts can be worked on? In general, we
  would assume overlaps are not possible.
- Time constraints. When does the deployment have to be completed by?
  (This also assumes estimation of the deployment time...)
- Dependencies between deployments.

Other considerations also factor in, such as the ability to roll a
deployment (example: 10 hosts at a time), or blue/green.

Such functionality may require significant human involvement,
especially at first; or it may be supplemented by a planner.

Example: enqueueing a deployment may trigger a ticket webhook to
complete processing by human completing all necessary aspects of
setting up the deployment.

(FIXME diagram showing this workflow)


Events (webhooks) -> Scheduler

The initial scheduler can be very simple: do one workflow at a time. Future variants should consider:

Time-based scheduling - workflows should be scheduled during maintenance windows
Overlaps
Dependency analysis
Shutdown immediately/gracefully



Cloud Management
----------------

Analytics-driven




Logical architecture
====================

FIXME insert appropriate diagram that shows elements of the process
flow and how they interact; also detail with swimlane diagrams



Inventory
=========

Backends

- Database
- System supporting the inventory REST API
- File-based, based on OSAD dynamic inventory


Import
------

Craton will provides support for importing inventory data from existing OSAD users:

http://docs.openstack.org/developer/openstack-ansible/developer-docs/inventory.html#inputs

(Can we also capture the UUIDs managed by this script? Certainly relevant for working with any existing deployments...)


Database backend
----------------

We will use a relational database to persist inventory
information. SQLAlchemy will be used for modeling, with Alembic
supporting migrations. For testing purposes, we expect SQLite to be
used; otherwise MySQL with Galera clustering is our target production
option. (This specifically may be Percona XtraDB.)

We will be using Ansible's inventory needs to drive these requirements:

FIXME update with the latest schema diagram

- Tenants - per customer, but a given customer may have multiple tenants.
- Hosts, identified by a synthetic `host_id`. Certain well-known host
  variables like IP address are available as nullable columns.
- Host variables/keys mapping, FK to hosts. This can also be used for
  extension attributes, eg to map to assets in a separate asset
  database.
- Groups, including subgroup relationships. Such groups also include
  other logical groupings like OpenStack regions and compute
  cells. Groups are strict trees; but a given host can belong to
  multiple such trees. Groups optionally reference configuration data
  via a URL, such as `GitHub refs
  <https://developer.github.com/v3/git/refs/>`_.
- Secrets, FK to hosts, stores a PEM encoded blob (possibly other
  formats). Secrets should be encrypted, with unlocking provided by
  retrieving a secret to unlock from a service like Barbican or Vault.

In many cases, operators will deploy a single tenant/single region
inventory, but this gives flexibility in terms of where the inventory
database is located - possibly co-located with the cloud region or
driving it externally.

Workflows may be filtered by using standard SQLAlchemy queries with
respect to regions; specific hosts; host variables (tagging); and
groups

Queries against the inventory database produce materialized inventory
files (tarballs) typically stored in `/etc/ansible/`. These can be
produced in aggregate: run the inventory for a given playbook across
many hosts; or as a bundle of inventory files per host for running by
TaskFlow wrapping Ansible, with both zip file and tgz available,
similar to what GitHub supports for downloads. Note that all blobs are
included in these tarballs.

Lastly, the inventory database is completely encapsulated by a REST
API, making it pluggable. For example, it is possible that an existing
asset management system/CMDB could provide the desired functionality
provided here. Alternatively, a different backend can be written, eg
with MongoDB.


Asset management
----------------

We expect that most organizations will be using their own asset
management database in conjunction with this inventory database. Such
asset management would also be linked against long-term historical
data.


Secret management
=================

`Barbican <http://docs.openstack.org/developer/barbican/api/reference/secrets.html>`_


REST API
========

APIs are versioned, so we start all with `/v1`. ACLs are managed at
the REST API level, and are in done in conjunction with (optional)
Keystone middleware.

`GET /v1/tenants`
-----------------

Retrieves all registered tenants.

`GET /v1/groups/{tenant_id}`
-----------------------------

Retrieve a list of groups for a given tenant, with some means to
restrict to a specific type of group, such as a region or cell.


`GET /v1/inventory/{group_id}.tgz`
-----------------------------------

Retrieves the tgz tarball bundle for running with TaskFlow. Optional
parameters can specify for direct with Ansible; and query filters (eg
a specific host key/value or group/subgroup).

TODO: define corresponding `POST`, `PUT`, and `DELETE` verbs as it
makes sense. Plus this is obviously just the beginning of the REST
API; it is also currently just looking at inventory.


Python API
==========

Wraps the REST API above.

All other usage of inventory in Craton uses the Python API, making it
possible to use another system to provide inventory data.


Scripting API
=============


Craton internals
================

Class layout FIXME (something initial with `tree` is probably good here)
