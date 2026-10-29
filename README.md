# aiida-polaron-MBPT

`aiida-polaron-MBPT` provides an AiiDA workflow for a staged polaron/MBPT calculation:

1. DFT+U ionic relaxation at Gamma.
2. A second DFT+U ionic relaxation with changed U values, restarting from the first calculation's stored wavefunctions.
3. A third DFT+U ionic relaxation with the second U values and a refined k-point mesh.
4. A DFT-only `YamboWorkflow` containing SCF, NSCF, GW, QP, and BSE, with BSE run on top of GW/QP results.

After stage 3, the workflow reports warnings if the largest final atomic force exceeds `0.2 eV/angstrom` or if any atom
moves more than `0.5 angstrom` from the initial structure. These thresholds can be set through
`max_force_threshold` and `max_structure_displacement`; the checks are warning-only for now.

The workflow uses `PwBaseWorkChain` configured with `CONTROL.calculation = "relax"`. This is intentional: the public
`PwRelaxWorkChain` interface excludes external `parent_folder` inputs, while `PwBaseWorkChain` supports the required
wavefunction restart directly.

## Installation

```bash
pip install -e /path/to/aiida-polaron-MBPT
```

The package requires compatible installations of `aiida-quantumespresso` and `aiida-yambo`.

## Hubbard input format

The `hubbard_u_initial` and `hubbard_u_final` inputs are `Dict` nodes. The recommended format is:

```python
orm.Dict(
    dict={
        "Fe": {"manifold": "3d", "value": 4.0},
    }
)
```

Values are in eV. The compact `{"Fe-3d": 4.0}` form is also accepted.

## Example

See [`examples/launch_polaron_mbpt.py`](examples/launch_polaron_mbpt.py). It shows how to configure QE, Yambo, the
QP subset settings, and the BSE parameters before calling `submit`.

## Authors

- Miki Bonacci, CNR ([@mikibonacci](https://github.com/mikibonacci))
- Savio Laricchia, CNR
