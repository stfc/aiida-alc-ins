Design Notes & Observations
============================

Key takeaways regarding design, architecture, and testing practices for an
`aiida-pythonjob <https://github.com/aiidateam/aiida-pythonjob>`_-based AiiDA plugin.

Practical Implications of PythonJob vs. Regular AiiDA Tasks
------------------------------------------------------------

Standard AiiDA tasks (``calcfunction`` and ``CalcJob``) require inputs and outputs to be explicit
AiiDA ``Data`` nodes (``StructureData``, ``Dict``, ``Int``, etc.):

- **calcfunction**: Runs locally in the active Python environment.
- **CalcJob**: Prepares input files, executes an external CLI tool or executable on a remote
  computer, and parses output files back into AiiDA ``Data`` nodes.

``PythonJob`` (and ``pyfunction``) allow tasks to be written as plain Python functions operating on
standard Python data types (primitives, dicts, NumPy arrays, ASE ``Atoms``, domain dataclasses).

Compared to a plain Python function, ``PythonJob`` combines two distinct behaviors:

1. **Remote execution**: Running the Python function on a target ``Computer`` (local engine,
   remote HPC cluster, or worker environment).
2. **Type casting at the provenance boundary**: Transparently converting native Python objects
   to/from AiiDA ``Data`` nodes so that inputs and results are stored in the AiiDA database with full
   provenance.

Constraints when Writing PythonJob and pyfunction Tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Functions must operate on native Python types**: A function wrapped for ``PythonJob`` *must* be
  written to accept and return non-AiiDA Python objects (e.g. NumPy arrays, dicts, ASE ``Atoms``, or
  domain dataclasses/classes). It cannot accept or instantiate AiiDA ``Data`` nodes directly.
- **Top-level functions required**: When supplying the ``function`` argument to
  ``prepare_pythonjob_inputs(function=...)`` (or ``@pyfunction``), ``aiida-pythonjob`` inspects
  ``function.__module__`` and ``function.__name__`` to generate remote import statements. Bound
  methods or classmethods (e.g. ``ForceConstants.from_castep_bin``) cannot be imported by reference
  directly and must be wrapped in thin, top-level module functions.
- **Custom AiiDA Data classes require boundary adapters**:

  - ``aiida-pythonjob`` automatically casts standard Python types (primitives, dicts, NumPy
    arrays, ASE ``Atoms``) to/from built-in AiiDA ``Data`` nodes (``Float``, ``Dict``,
    ``ArrayData``, ``StructureData``).
  - However, if a step's output should be represented in the database by a custom AiiDA ``Data``
    class (or specific node type), the task function cannot create or return that AiiDA node
    directly. Instead, the function must return a native Python object, and you must write
    conversion functions (serializers and deserializers) or adapter classes to bridge the native
    Python object and your custom AiiDA ``Data`` class at the boundary.

Isolation of AiiDA ORM from PythonJob Functions
------------------------------------------------

Functions executed via ``PythonJob`` **must not** import ``aiida`` or manipulate AiiDA ORM objects
(``aiida.orm.Node``, ``StructureData``, etc.):

1. **No remote AiiDA database**: Remote execution environments (HPC worker nodes, container
   runners) do not run AiiDA daemons or hold database connections. Importing ``aiida.orm`` remotely
   will fail or require an active database profile.
2. **Separation of concerns**: The idea of ``aiida-pythonjob`` is to keep scientific functions
   pure (operating on ASE ``Atoms``, NumPy arrays, or domain Python classes) and free of workflow
   infrastructure.

Once we're past the data-wrangling identified in point 1, this restriction is probably a good
thing. Write the "business logic" as pure functions that operate on the data they are given: these
are easier to develop and test.

Recommended Project Layout
~~~~~~~~~~~~~~~~~~~~~~~~~~

A clean pattern is to place pure calculation routines in a dedicated module (``operations.py``)
with an **AiiDA-free import chain**, and keep process input builders (``prepare_*_inputs``) in a
separate module (``pythonjobs.py``). This guarantees that remote unpickling imports only
scientific dependencies without triggering AiiDA configuration, and enables fast unit testing of
business logic without AiiDA test profiles.

Serializer and Deserializer Architecture
----------------------------------------

Native Python objects <-> AiiDA ``Data`` node conversions are handled by ``serializer`` and
``deserializer`` mappings in ``aiida-pythonjob``.

Registration occurs across three tiers in ascending order of priority:

1. **Package entry points (install-level)**: Registered in ``pyproject.toml`` under
   ``aiida_pythonjob.serializers`` and ``aiida_pythonjob.deserializers``. This is the standard.
2. **Configuration file**: Registered in ``~/.aiida/config.json`` under ``pythonjob.serializers``.
3. **Runtime invocations**: Passed explicitly per call via
   ``prepare_pythonjob_inputs(serializers=..., deserializers=...)`` (as used in this prototype).

Remote Execution, Pickling, and register_pickle_by_value
--------------------------------------------------------

When launching a ``PythonJob``, ``aiida-pythonjob`` uses ``cloudpickle`` to serialize the target
Python function. The ``register_pickle_by_value`` parameter determines how module references are
pickled:

- **Pickle by reference (register_pickle_by_value=False, default)**: Sends light module import
  references (e.g., ``import my_package.ops; my_package.ops.my_func``). Payload size is minimal
  (tens of bytes). Requires ``my_package`` to be pre-installed in the remote Python environment.
- **Pickle by value (register_pickle_by_value=True)**: Serializes pure-Python function bytecode,
  AST, and scope directly into the pickle stream.

Recommendation
~~~~~~~~~~~~~~

Always use ``register_pickle_by_value=False`` (default) and require the plugin package to be
installed in both local and remote environments.

1. **Compiled & C-extension dependencies**: ``cloudpickle`` can only pickle pure-Python code by
   value. It **cannot** pickle C-extensions, compiled shared libraries, or heavy binary packages
   (``euphonic``, ``numpy``, ``scipy``, ``spglib``). The remote environment **must still have all
   underlying scientific dependencies installed**.
2. **Payload size**: Pickling by value increases payload bandwidth (sending kilobytes or
   megabytes of bytecode vs bytes of import references).
3. **Traceability**: Unpickling bytecode on remote hosts produces anonymous stack traces
   (``<string>:1``), making remote failure debugging harder compared to installed packages with named
   source files.
4. **Simpler packaging**: The requirement for remote becomes "install this package" rather than
   "install this subset of packages from a requirements.txt we probably forgot to update".
5. **Simpler testing**: Unit tests can use ``sys.executable`` as the interpreter for its Python
   Code and get the correct environment "for free".

Pytest Setup and Test Fixtures
------------------------------

Testing an ``aiida-pythonjob`` plugin requires initializing an ephemeral AiiDA profile and
configuring a Python execution ``Code`` node on localhost.

Useful Practices in conftest.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **get_config before imports**: ``aiida-pythonjob`` accesses ``get_config()`` at import time
   when building its serializer registry. If ``pytest`` collects test modules before a profile
   fixture runs, importing the package without an existing ``~/.aiida`` directory raises
   ``MissingConfigurationError``. The workaround is to call ``get_config(create=True)`` before
   importing any AiiDA-based modules, creating an initialized bare config if there wasn't one.
2. **Use a temporary AIIDA_PATH**: To avoid requiring or modifying the developer's own ``.aiida``
   directory, set ``AIIDA_PATH`` in ``os.environ`` to a temporary directory *before* calling ``get_config``.
3. **Enable AiiDA pytest fixtures**: ``pytest_plugins = [aiida.tools.pytest_fixtures]``
   enables official AiiDA fixtures (such as ``aiida_profile``, ``aiida_localhost``,
   and ``aiida_code_installed``) providing a suitable environment for tests that
   interact with AiiDA.
4. **Localhost python_code fixture**: Define a ``python_code`` fixture using ``aiida_code_installed``
   setting the default calculation job plugin to ``pythonjob.pythonjob`` and executable filepath to ``sys.executable``.
   Pointing to ``sys.executable`` runs test ``PythonJob`` processes in the active virtual environment where the
   plugin and its dependencies are installed.
5. **Data fixtures**: ``conftest.py`` is also the right place to set up shared pytest fixtures used
   across multiple test files. If a fixture is only used in one file, define it there instead.

Parallel Test Execution
~~~~~~~~~~~~~~~~~~~~~~~

The project runs tests in parallel by default. ``pytest-xdist`` is declared in the
default dev dependencies, and ``pyproject.toml`` sets ``addopts = ["-n", "auto"]``
under ``[tool.pytest.ini_options]``, so ``uv run pytest`` distributes the suite
across all available CPU cores without extra flags.

The containerized integration tests use a session-scoped
``remote_container_info`` fixture to coordinate a single shared
SSH/HyperQueue container across worker processes. This is implemented
with a ``filelock.FileLock`` on a shared ``container_info.json``
(written by the first worker, reused by the rest), and a
``pytest_sessionfinish`` hook tears the container down from the
controller process only. A ``worker_id`` stub is provided for runs
without xdist. Simpler mechanisms are likely possible: the main thing
is to avoid spawining one container per xdist worker, and instead let
hyperqueue manage jobs from the workers against available CPU resources.

To run tests sequentially (e.g. for debugging or clearer tracebacks), pass
``-n 0`` to disable the worker pool:

.. code-block:: bash

   uv run pytest -n 0
