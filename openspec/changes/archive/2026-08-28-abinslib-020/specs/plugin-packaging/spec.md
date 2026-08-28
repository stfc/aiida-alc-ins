## MODIFIED Requirements

### Requirement: Dependency bounds are justified by this package's own usage

Dependency constraints SHALL be derived from the APIs this package actually uses,
not copied from the constraints of sibling dependencies. Upper caps SHALL be
applied only where individually justified, because a resolver intersects the
requirements of every co-installed plugin and needlessly narrow pins cause
avoidable conflicts. The package SHALL pin `abinslib~=0.2.0` from PyPI to match
the decoupled weighting API introduced in abinslib 0.2.

#### Scenario: Each dependency records its rationale

- **WHEN** the declared dependencies are reviewed
- **THEN** each carries a stated reason for its lower bound and for any upper cap
- **AND** `abinslib` is declared as `~=0.2.0` from PyPI

#### Scenario: A sibling's transitive constraint is not restated

- **WHEN** a dependency of this package imposes its own stricter requirement on a
  shared dependency
- **THEN** this package does not restate that requirement, leaving the resolver to
  enforce it
