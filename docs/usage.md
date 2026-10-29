# Usage

The workflow is launched like any other AiiDA workchain: fill a builder and `submit` it. Two complete scripts are in the [`examples/`](https://github.com/mikibonacci/aiida-polaron-MBPT/tree/main/examples) folder, explained on the [Examples](examples.md) page.

## Minimal skeleton

```python
from aiida import load_profile, orm
from aiida.engine import submit
from aiida_polaron_mbpt.workflows.polaron_mbpt import PolaronMBPTWorkChain

load_profile()

builder = PolaronMBPTWorkChain.get_builder()
builder.structure = structure                      # orm.StructureData
builder.pw_code = orm.load_code("pw@cluster")
builder.yambo_code = orm.load_code("yambo@cluster")
builder.yambo_preprocessing_code = orm.load_code("p2y@cluster")
builder.pseudo_family = orm.Str("PseudoDojo/0.4/PBE/SR/standard/upf")

gamma = orm.KpointsData()
gamma.set_kpoints_mesh((1, 1, 1))
refined = orm.KpointsData()
refined.set_kpoints_mesh((2, 2, 2))
builder.kpoints_gamma = gamma
builder.kpoints_relax3 = refined

builder.hubbard_u_initial = orm.Dict(dict={"Ti1": {"manifold": "3d", "value": 3.5}})
builder.hubbard_u_final = orm.Dict(dict={"Ti1": {"manifold": "3d", "value": 3.5}})

for stage in ("relax_1", "relax_2", "relax_3"):
    builder[stage].pw.parameters = qe_parameters   # orm.Dict, as for PwBaseWorkChain
    builder[stage].pw.metadata.options = {...}     # resources and walltime

# builder.yambo: SCF/NSCF/QP/BSE inputs, see below

node = submit(builder)
```

## Hubbard U

`hubbard_u_initial` and `hubbard_u_final` are `Dict` nodes keyed by kind name:

```python
orm.Dict(dict={"Fe": {"manifold": "3d", "value": 4.0}})
```

Values are in eV. The compact `{"Fe-3d": 4.0}` form is also accepted. Kinds are matched by name, so to give different U values to atoms of the same element, give them different kind names in the structure (for example `Ti1`, `Ti2`). The projectors and formulation default to `atomic` and `dudarev` and can be changed with `hubbard_projectors` and `hubbard_formulation`.

## The Yambo part

The `builder.yambo` namespace has the inputs of `YamboWorkflow`, minus what the outer workchain supplies itself: the structure, the codes, the pseudopotentials, the k-points and the parent folder. The simplest way to fill it is to take `YamboWorkflow.get_builder_from_protocol` plus `YamboInputManager` and copy the configurable inputs, as `configure_yambo_from_protocol` does in the high-level example.

If `kpoints_yambo` is not given, the Yambo SCF/NSCF use `kpoints_relax3`.

## Quality checks

After the third relaxation the workflow reports a warning if the largest final force exceeds `max_force_threshold` (default 0.2 eV/Å) or if any atom moved more than `max_structure_displacement` (default 0.5 Å) from the initial structure. Both checks only warn for now. Look for them with:

```bash
verdi process report <pk>
```
