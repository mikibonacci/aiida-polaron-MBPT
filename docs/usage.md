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

The two dictionaries have different roles. `hubbard_u_initial` is what localizes the extra electrons and so makes the polaron form: give a much larger U to one atom per additional electron (for example one Ti per H adsorbed on the slab), and the physical U to the others. The large difference is what localizes the electron and forms the polaron. `hubbard_u_final` is the U you want for the final calculation, on all atoms. See [Concepts](concepts.md#how-the-polaron-is-formed).

Values are in eV. The compact `{"Fe-3d": 4.0}` form is also accepted. Kinds are matched by name, so to give different U values to atoms of the same element, give them different kind names in the structure (for example `Ti1`, `Ti2`). The projectors and formulation default to `atomic` and `dudarev` and can be changed with `hubbard_projectors` and `hubbard_formulation`.

## The structure: the candidate atom needs its own kind

The U values are assigned per kind, through the `HubbardStructureData` that the workflow builds for each stage. So the atom that should host the extra electron must have a different kind name from the other atoms of the same element. If it does not, it cannot get a different U, and the polaron will not form.

```python
structure = orm.StructureData(cell=cell, pbc=(True, True, True))
structure.append_atom(position=pos_a, symbols="Ti", name="Ti1")   # all the "normal" Ti atoms
structure.append_atom(position=pos_b, symbols="Ti", name="Ti1")
structure.append_atom(position=pos_c, symbols="Ti", name="Ti2")   # the candidate: its own kind
```

```python
builder.hubbard_u_initial = orm.Dict(dict={
    "Ti1": {"manifold": "3d", "value": 3.5},
    "Ti2": {"manifold": "3d", "value": 10.0},   # much larger: localizes the polaron
})
builder.hubbard_u_final = orm.Dict(dict={
    "Ti1": {"manifold": "3d", "value": 3.5},
    "Ti2": {"manifold": "3d", "value": 3.5},
})
```

When the structure comes from an ASE `Atoms` object, set the tags: `StructureData(ase=atoms)` names a kind as the symbol plus the tag, so tag 2 on a Ti atom gives the kind `Ti2`. Check the result with `structure.get_kind_names()` before submitting.

### More than one high-U site

You can have several high-U sites, typically one per extra electron (for example one Ti per adsorbed H). There are two ways to set them up, since U is assigned per kind:

- **One kind per site** (`Ti2`, `Ti3`, ...). Each site gets its own entry in the Hubbard dictionaries. Use this when the sites need different settings, for example opposite starting magnetizations for antiparallel spins, or different U values.
- **One shared kind** for all the high-U sites (for example `Ti2` on every candidate). All the atoms of that kind get the same U and the same starting magnetization.

```python
builder.hubbard_u_initial = orm.Dict(dict={
    "Ti1": {"manifold": "3d", "value": 3.5},
    "Ti2": {"manifold": "3d", "value": 10.0},   # first high-U site
    "Ti3": {"manifold": "3d", "value": 10.0},   # second high-U site
})
```

In all cases, `hubbard_u_final` should list every kind, so that U is back to the physical value for the second and third relaxations. Give each of these kinds its own starting magnetization too if the calculation is spin-polarized.

## The Yambo part

The `builder.yambo` namespace has the inputs of `YamboWorkflow`, minus what the outer workchain supplies itself: the structure, the codes, the pseudopotentials, the k-points and the parent folder. The simplest way to fill it is to take `YamboWorkflow.get_builder_from_protocol` plus `YamboInputManager` and copy the configurable inputs, as `configure_yambo_from_protocol` does in the high-level example.

If `kpoints_yambo` is not given, the Yambo SCF/NSCF use `kpoints_relax3`.

## Quality checks

After the third relaxation the workflow reports a warning if the largest final force exceeds `max_force_threshold` (default 0.2 eV/Å) or if any atom moved more than `max_structure_displacement` (default 0.5 Å) from the initial structure. Both checks only warn for now. Look for them with:

```bash
verdi process report <pk>
```
