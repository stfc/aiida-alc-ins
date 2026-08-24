## MODIFIED Requirements

### Requirement: Plugin classes are discoverable through AiiDA entry points

The package SHALL register its data types under the `aiida.data` entry-point group
and its workflows under `aiida.workflows`, using the `pythonjob_ins` prefix, so
that AiiDA users can load them through the standard plugin factories rather than
by direct import. The registered set SHALL cover every data type and workflow
intended for users to load, so introducing one is a modification to this
requirement and to the scenarios below.

Where two workflows perform the same calculation from different starting data,
their entry-point names SHALL distinguish them by that starting data, since the
result alone does not.

#### Scenario: Data classes load through the data factory

- **WHEN** `pythonjob_ins.crystal`, `pythonjob_ins.force_constants` or
  `pythonjob_ins.qpoint_phonon_modes` is requested from AiiDA's data factory
- **THEN** the corresponding `EuphonicCrystalData`, `ForceConstantsData` or
  `QpointPhononModesData` class is returned

#### Scenario: Workflows load through the workflow factory

- **WHEN** `pythonjob_ins.dispersion`, `pythonjob_ins.dos`,
  `pythonjob_ins.tosca_from_modes` or `pythonjob_ins.tosca_from_force_constants`
  is requested from AiiDA's workflow factory
- **THEN** the corresponding `DispersionWorkChain`, `DosWorkChain`,
  `ToscaFromModesWorkChain` or `ToscaFromForceConstantsWorkChain` class is
  returned

#### Scenario: Every declared entry point resolves to its class

- **WHEN** the installed AiiDA plugins are listed for the `aiida.data` and
  `aiida.workflows` groups
- **THEN** every entry point this package declares is listed, and each loads the
  class it names

## ADDED Requirements

### Requirement: Serializer registry keys track the classes they name

The mapping from scientific object types to the AiiDA nodes that store them is
keyed by the type's import path, resolved as text at run time. A key that no
longer matches its type does not raise: the object silently falls back to generic
storage and a workflow receives a node of the wrong type.

Registry keys SHALL therefore be derived from the classes themselves rather than
written out by hand, so that a key follows its class if the class is relocated
upstream. Every registered key SHALL be verifiable as naming a real, importable
class, so that a relocation the package does not otherwise notice is reported.

#### Scenario: Every registry key names an importable class

- **WHEN** the registered mappings are inspected
- **THEN** every key resolves to a class that can be imported

#### Scenario: A registered type is stored as its intended node type

- **WHEN** a job returns an object of a registered type
- **THEN** the resulting node is of the type the registry names for it, not a
  generic fallback
