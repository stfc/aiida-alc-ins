# Bundled sample data provenance

## `ethanol_qpoint_phonon_modes.json`

A gamma-point Euphonic `QpointPhononModes` dump for a molecular ethanol crystal
(9 atoms: 2 C, 1 O, 6 H), used as the TOSCA tutorial's example dataset because
TOSCA's almost-isotropic incoherent approximation is most representative for
hydrogenous, molecular samples (see
`openspec/changes/archive/2026-08-24-abinslib-workflow/design.md`, "13. Bundled
sample data", and
`openspec/changes/archive/2026-08-24-abinslib-workflow/proposal.md` — Why).

- **Origin**: [`isisneutronmuon/abINS_lib`](https://github.com/isisneutronmuon/abINS_lib),
  `tests/data/ethanol_qpoint_phonon_modes.json`
- **Upstream commit**: `c308b4ba045074ff3e94a4cd214eec31c3021534`
- **SHA-256**: `c0c3f306e44acec8db746e8e64c1af9936015759f0f76fe10e2d94101ad7a7f9`

## `phonopy/NaCl_hdf5/`

Phonopy output for rock-salt NaCl (8 atoms), used to test the Phonopy reader
with HDF5 force constants and the `phonopy` source of
`ForceConstantsWorkChain`. The four files keep their upstream names:

- `phonopy_nofc_noborn.yaml`: summary with neither force constants nor Born
  data;
- `force_constants.hdf5`: HDF5 force constants for that summary;
- `BORN_nacl`: Born charges and dielectric tensor;
- `phonopy_nacl.yaml`: summary with embedded force constants and Born data.

- **Origin**: [`pace-neutrons/Euphonic`](https://github.com/pace-neutrons/Euphonic),
  `tests_and_analysis/test/data/phonopy_files/NaCl/`
- **Upstream commit**: `1d86683518f248f621539c2ddcbf7964b061b439`
- **SHA-256**:
  - `phonopy_nofc_noborn.yaml`: `c71e9685963a3a5988b93d0b68f7f61cc089a54d51ba0f99a7fe7d5aa6bbe001`
  - `force_constants.hdf5`: `1d3b038fc40dd4107289c1495307a6b72af7036a2710c6f6cf548de0ae86966e`
  - `BORN_nacl`: `3961e05e92a9776f0e0bd578f35880525329335271d93cce9688447f65e8b68e`
  - `phonopy_nacl.yaml`: `8a0aa1d1e5c6f0631bbe6ef405565ea1cfb4c6ce3fb370960c55075309a3a4a2`
