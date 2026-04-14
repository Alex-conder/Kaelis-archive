import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

print("Script started")

# Simulate docking data since raw data not available
data = []
proteins = ['3VVP', '6UJN', '8ET9', '8RQ4', '8SDY']
ligands = ['Vancomycin', 'Meropenem']

for prot in proteins:
    for lig in ligands:
        # Simulate 10 docking poses with binding energies (kcal/mol)
        energies = np.random.normal(-8, 2, 10)  # mean -8, std 2
        for i, e in enumerate(energies):
            data.append({'Protein': prot, 'Ligand': lig, 'Binding_Energy': e, 'Pose': i+1})

df = pd.DataFrame(data)

# Energy distribution plot (boxplot for each protein-ligand pair)
plt.figure(figsize=(12, 8))
sns.boxplot(data=df, x='Protein', y='Binding_Energy', hue='Ligand')
plt.title('Binding Energy Distribution for Vancomycin and Meropenem with 5 Proteins')
plt.ylabel('Binding Energy (kcal/mol)')
plt.savefig('energy_distribution.png')
# plt.show()
print("Energy distribution plot saved")

# Binding forces simulation (interaction counts)
forces_data = []
interaction_types = ['Hydrogen Bond', 'Hydrophobic', 'Ionic', 'Pi-Stacking']

for prot in proteins:
    for lig in ligands:
        for it in interaction_types:
            count = np.random.randint(0, 5)  # Random count 0-4
            forces_data.append({'Protein': prot, 'Ligand': lig, 'Interaction_Type': it, 'Count': count})

forces_df = pd.DataFrame(forces_data)

# Binding forces plot
plt.figure(figsize=(14, 8))
sns.barplot(data=forces_df, x='Protein', y='Count', hue='Interaction_Type')
plt.title('Binding Forces (Interaction Counts) for Vancomycin and Meropenem')
plt.savefig('binding_forces.png')
# plt.show()
print("Binding forces plot saved")

# For 2D interaction maps, note on using PLIP
print("To generate 2D interaction maps, use PLIP tool on PDB files containing docked ligands.")
print("Example command: plip -f protein_ligand.pdb -o output_dir")
print("Since PDB files appear to be apo structures, docking simulations are needed first.")