# Spec Delta: documentation

## MODIFIED Requirements

### Requirement: Workflow interfaces are documented from their runtime spec

A WorkChain's interface is defined at runtime and is invisible to static analysis,
which would otherwise expose only its internal step methods. The documentation
SHALL therefore render workflow interfaces from the live process specification,
and SHALL keep the misleading static view out of the API reference. The workflow
documentation SHALL explicitly document the WorkChain exit codes defined by the
package (including exit code 400 `ERROR_SUB_PROCESS_FAILED`). Each workflow's
description SHALL be rendered as formatted documentation, with its markup
interpreted rather than shown as source text.

#### Scenario: A workflow page shows its real interface

- **WHEN** the documentation is built
- **THEN** each workflow's page lists its actual inputs, outputs, exit codes and outline

#### Scenario: Workflow descriptions are rendered, not shown as source

- **WHEN** the documentation is built
- **THEN** no workflow description on a workflow page shows reStructuredText
  syntax, such as roles or double-backtick literals, as literal text
- **AND** references and inline literals in a description are formatted as
  code, linking to their target wherever that target is documented
- **AND** list structure in a description, such as the exit-code list, is
  rendered as a list

#### Scenario: Outline methods are not presented as the public interface

- **WHEN** the generated API reference is built
- **THEN** WorkChain classes are excluded from it, so their internal step methods
  are not shown in place of their interface
