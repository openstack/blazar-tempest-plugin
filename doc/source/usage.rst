=====
Usage
=====

The api tests are defined in .yaml files and should be executed
in the order in the file. To do this, set ``group_regex`` parameter
in ``.stestr.conf``::

    group_regex=blazar_tempest_plugin\.tests\.api\.test_blazar_api

or, you can also save the test order by setting the number of test
workers to one via tempest run options::

    $ tempest run --regex blazar_tempest_plugin --serial

or::

    $ tempest run --regex blazar_tempest_plugin --concurrency=1

