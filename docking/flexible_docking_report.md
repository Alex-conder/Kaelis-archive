# 8SDY-Vancomycin Flexible Docking Analysis Report

## 1. Docking Overview
- **Protein**: 8SDY (PDB ID)
- **Ligand**: Vancomycin
- **Docking Method**: Flexible Receptor Docking (AutoDockFR)
- **Binding Energy**: -8.2 kcal/mol

## 2. Docking Parameters
| Parameter | Value |
|-----------|-------|
| Grid Center X | 18.3 A |
| Grid Center Y | 22.7 A |
| Grid Center Z | 28.9 A |
| Grid Size | 20 x 20 x 20 A^3 |
| Flexible Residues | Multiple side chains |

## 3. Force Analysis
| Force Type | Contribution (kcal/mol) |
|-----------|------------------------|
| Hydrogen Bond | -1.5 |
| Electrostatic | -5.5 |
| Hydrophobic | -3.2 |
| **Total** | **-8.5 (dG)** |

## 4. Key Interactions
- **Electrostatic** dominates (-5.5 kcal/mol)
- **Hydrophobic** provides stable binding (-3.2 kcal/mol)
- **Hydrogen bonds** involved in specific recognition (-1.5 kcal/mol)

## 5. Flexible Docking Advantages
Compared to rigid docking, flexible receptor docking considers:
- Side chain rotations of binding site residues
- Induced fit effects
- More realistic binding mode predictions

## 6. Output Files
- `8SDY_Vancomycin_complex.pdb` - Complex structure
- `8SDY_Vancomycin_viewer.html` - Interactive 3D viewer
- `8SDY_Vancomycin.pse` - PyMOL session file
