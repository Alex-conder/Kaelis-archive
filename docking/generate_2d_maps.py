from plip.structure.preparation import PDBComplex
from plip.exchange.report import BindingSiteReport
import os

print("Starting 2D interaction map generation")

# Assuming PDB files contain docked ligands
pdbs = ['3VVP.pdb', '6UJN.pdb', '8ET9.pdb', '8RQ4.pdb', '8SDY.pdb']

for pdb_file in pdbs:
    if os.path.exists(pdb_file):
        my_mol = PDBComplex()
        my_mol.load_pdb(pdb_file)
        my_mol.analyze()
        
        for ligand in my_mol.ligands:
            print(f"Generating 2D interaction map for {pdb_file} with {ligand}")
            # Create binding site report
            report = BindingSiteReport(my_mol.interaction_sets[ligand])
            # Save 2D interaction map
            output_file = f'2d_interaction_{pdb_file.replace(".pdb", "")}_{ligand}.png'
            report.write_2d_interaction_map(output_file)
            print(f"Saved {output_file}")
    else:
        print(f"PDB file {pdb_file} not found")

print("2D interaction map generation complete. Note: If PDB files do not contain ligands, docking simulations are required first.")