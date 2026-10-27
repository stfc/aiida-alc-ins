Workflows
=========

The high-level ``WorkChain``\ s and their inputs/outputs. ``ForceConstantsWorkChain``
resolves a force-constants source (a CASTEP ``castep_file`` or a pre-built
``node``) into a ``ForceConstantsData``; it is also runnable standalone. The
workflows that start from force constants -- ``DispersionWorkChain``,
``DosWorkChain`` and ``ToscaFromForceConstantsWorkChain`` -- run it as a
sub-workflow, grouping its inputs under a single ``force_constants`` namespace
(e.g. ``force_constants={"castep_file": f}`` or ``force_constants={"node": fc}``).
``ToscaFromModesWorkChain`` instead starts from precomputed phonon modes and
offers no force-constants source at all -- see the worked
:doc:`examples <auto_examples/index>`. To build a workflow of your own on top of
``ForceConstantsWorkChain``, see :ref:`building-on-force-constants` below.

These pages are generated from the live process **spec** by AiiDA's
``aiida-workchain`` directive, showing the inputs, outputs, and outline, with
exit codes listed in each workflow's description.

.. aiida-workchain:: ForceConstantsWorkChain
   :module: aiida_pythonjob_ins.workflows.force_constants

.. aiida-workchain:: DispersionWorkChain
   :module: aiida_pythonjob_ins.workflows.dispersion

.. aiida-workchain:: DosWorkChain
   :module: aiida_pythonjob_ins.workflows.dos

.. aiida-workchain:: ToscaFromModesWorkChain
   :module: aiida_pythonjob_ins.workflows.tosca

.. aiida-workchain:: ToscaFromForceConstantsWorkChain
   :module: aiida_pythonjob_ins.workflows.tosca

.. _building-on-force-constants:

Building your own workflow on ``ForceConstantsWorkChain``
---------------------------------------------------------

``ForceConstantsWorkChain`` is the building block for getting force constants
onto the provenance graph. You can launch it on its own, or run it as a child of
a workflow of your own. Whichever source the caller supplies, your workflow gets
a ``ForceConstantsData`` back, and as more input formats are supported, your
workflow picks them up without any changes.

The shortcut: ``FromForceConstantsWorkChain``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The workflows in this package all use ``ForceConstantsWorkChain`` the same way,
so that shared code lives in one helper base class,
``FromForceConstantsWorkChain`` (in ``aiida_pythonjob_ins.workflows.base``).
Its name says what it is for: workflows that start *from* force constants. It
does not inherit from ``ForceConstantsWorkChain``. Instead, it runs
``ForceConstantsWorkChain`` for you. Inheriting it gives your workflow:

* a ``force_constants`` input group, holding the same inputs as
  ``ForceConstantsWorkChain`` (``castep_file`` or ``node``);
* two outline steps, ``run_force_constants`` and ``inspect_force_constants``,
  which run the child and collect its result. They are two steps because a
  WorkChain submits a child in one step and the engine resumes it in the next,
  once the child has finished; see AiiDA's `Submitting sub processes
  <https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/workflows/usage.html#submitting-sub-processes>`_;
* exit code ``402 ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS`` if the child fails;
* the resolved ``ForceConstantsData`` in ``self.ctx.force_constants``.

A minimal example:

.. code-block:: python

    from aiida_pythonjob_ins.workflows.base import FromForceConstantsWorkChain


    class MyWorkChain(FromForceConstantsWorkChain):
        @classmethod
        def define(cls, spec):
            super().define(spec)
            spec.outline(
                cls.run_force_constants,
                cls.inspect_force_constants,
                cls.analyse,
            )

        def analyse(self):
            force_constants = self.ctx.force_constants  # a ForceConstantsData
            ...

Callers then pass the source just as they would to ``DispersionWorkChain``, for
example ``force_constants={"castep_file": f}``. If your workflow also
dispatches PythonJobs, inherit ``JobDispatchWorkChain`` from the same module
as well, as ``DispersionWorkChain`` does, to get the ``code`` and ``options``
inputs and exit code 400.

Composing it directly
~~~~~~~~~~~~~~~~~~~~~

The shortcut is a convenience, not a requirement. It suits workflows that need
one source and resolve it first. If yours doesn't, run
``ForceConstantsWorkChain`` yourself with AiiDA's ``expose_inputs`` and
``exposed_inputs``. For example:

* your workflow needs **several sources**, such as two calculations to compare;
* it resolves force constants **later**, or only under some condition;
* it accepts **only some sources**, for example exposing just ``castep_file``
  with ``include=["castep_file"]``;
* it **handles failure differently**, for example falling back to another
  source.

Here is a workflow that compares two sources:

.. code-block:: python

    from aiida.engine import ToContext, WorkChain

    from aiida_pythonjob_ins.workflows import ForceConstantsWorkChain


    class CompareWorkChain(WorkChain):
        @classmethod
        def define(cls, spec):
            super().define(spec)
            spec.expose_inputs(ForceConstantsWorkChain, namespace="first")
            spec.expose_inputs(ForceConstantsWorkChain, namespace="second")
            spec.outline(cls.resolve_both, cls.compare)
            spec.exit_code(
                402,
                "ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS",
                message="A ForceConstantsWorkChain sub-workflow did not finish successfully.",
            )

        def resolve_both(self):
            return ToContext(
                first=self.submit(
                    ForceConstantsWorkChain,
                    **self.exposed_inputs(ForceConstantsWorkChain, namespace="first"),
                ),
                second=self.submit(
                    ForceConstantsWorkChain,
                    **self.exposed_inputs(ForceConstantsWorkChain, namespace="second"),
                ),
            )

        def compare(self):
            if not (self.ctx.first.is_finished_ok and self.ctx.second.is_finished_ok):
                return self.exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS
            first = self.ctx.first.outputs.force_constants
            second = self.ctx.second.outputs.force_constants
            ...

Callers write ``first={"castep_file": f}, second={"node": fc}``. Each group
checks on its own that exactly one source was given.

The one rule
~~~~~~~~~~~~

However you compose it, go through ``ForceConstantsWorkChain`` rather than
reading force-constants files yourself. That keeps all the source handling in
one place, so new formats and fixes reach every workflow, including yours.
