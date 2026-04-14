
# PyMOL script: Generate 8SDY-Vancomycin 3D docking pose
reinitialize

# Load protein and ligand
load C:\Users\11526\OneDrive\Desktop\docking\8SDY.pdb, protein
color skyblue, protein
as cartoon, protein

# Load ligand
load C:\Users\11526\OneDrive\Desktop\docking\3d_flexible_results\Vancomycin_docked.pdb, ligand
color lime, ligand
as sticks, ligand
show spheres, ligand
set sphere_scale, 0.3, ligand

# Center on ligand
center ligand
zoom ligand, 10

# Show hydrogen bonds
distance hbonds, protein, ligand, 3.5, mode=2
set dash_gap, 0.2
set dash_radius, 0.1

# Add label
label ligand, "Vancomycin"

# Set background
bg_color white
set antialias, 2
set ray_trace_mode, 1

# Save session
save C:\Users\11526\OneDrive\Desktop\docking\3d_flexible_results\8SDY_Vancomycin.pse

# Render image
ray 1920, 1080
png C:\Users\11526\OneDrive\Desktop\docking\3d_flexible_results\8SDY_Vancomycin.png, dpi=300

print "PyMOL session saved"
