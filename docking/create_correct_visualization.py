#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用正确的3D配体生成可视化
"""

from __future__ import print_function
import os
import shutil

BASE_DIR = r"C:\Users\11526\OneDrive\Desktop"
DOCKING_DIR = os.path.join(BASE_DIR, "docking")
OUTPUT_DIR = os.path.join(DOCKING_DIR, "CORRECT_3D_RESULTS")

PROTEIN_FILE = os.path.join(DOCKING_DIR, "8SDY.pdb")
LIGAND_PDB = os.path.join(DOCKING_DIR, "Vancomycin_3D.pdb")


def create_complex(protein_pdb, ligand_pdb, output_complex):
    """创建蛋白-配体复合物"""
    print("Creating complex structure...")
    
    with open(output_complex, 'w') as outfile:
        # 写入蛋白 (链A)
        if os.path.exists(protein_pdb):
            with open(protein_pdb, 'r') as f:
                for line in f:
                    if line.startswith('ATOM') or line.startswith('HETATM'):
                        outfile.write(line)
                    elif line.startswith('END'):
                        break
        
        outfile.write("TER\n")
        
        # 写入配体 (链B, 残基名VAN)
        if os.path.exists(ligand_pdb):
            with open(ligand_pdb, 'r') as f:
                atom_num = 10001
                res_num = 1
                for line in f:
                    if line.startswith('HETATM') or line.startswith('ATOM'):
                        # 提取坐标
                        x = line[30:38]
                        y = line[38:46]
                        z = line[46:54]
                        atom_name = line[12:16] if len(line) > 16 else ' C  '
                        element = line[76:78] if len(line) > 78 else 'C'
                        
                        new_line = "HETATM{:5d} {:4s} VAN B{:4d}    {:8s}{:8s}{:8s}  1.00  0.00          {:>2s}\n".format(
                            atom_num, atom_name.strip(), res_num, x, y, z, element.strip()
                        )
                        outfile.write(new_line)
                        atom_num += 1
        
        outfile.write("END\n")
    
    print("Complex created: {}".format(output_complex))
    return output_complex


def generate_html_viewer(complex_pdb, output_html):
    """生成HTML查看器"""
    print("Generating HTML viewer...")
    
    with open(complex_pdb, 'r') as f:
        pdb_data = f.read()
    
    # Escape for JavaScript
    pdb_data = pdb_data.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
    
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>8SDY-Vancomycin CORRECT 3D Structure</title>
    <meta charset="UTF-8">
    <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
    <style>
        body {{ margin: 0; font-family: Arial, sans-serif; background: #1a1a2e; color: white; }}
        #viewport {{ width: 100%; height: 80vh; position: relative; }}
        #controls {{ padding: 15px; background: #16213e; }}
        .button {{ background: #0f3460; color: white; border: none; padding: 10px 20px; 
                   margin: 5px; cursor: pointer; border-radius: 5px; font-size: 14px; }}
        .button:hover {{ background: #e94560; }}
        .success {{ color: #4ecca3; }}
        .warning {{ color: #ffd700; }}
        h1 {{ margin: 0 0 10px 0; font-size: 20px; }}
        .info {{ display: inline-block; margin-left: 20px; }}
    </style>
</head>
<body>
    <div id="controls">
        <h1>8SDY-Vancomycin <span class="success">[CORRECT 3D]</span></h1>
        <p class="warning">This is the FIXED structure with proper 3D coordinates</p>
        <button class="button" onclick="showSurface()">Protein Surface</button>
        <button class="button" onclick="showCartoon()">Cartoon</button>
        <button class="button" onclick="showLigand()">Focus Ligand</button>
        <button class="button" onclick="showComplex()">Full Complex</button>
        <button class="button" onclick="resetView()">Reset</button>
        <button class="button" onclick="toggleSpin()">Spin</button>
        <div class="info">
            <span style="color:#4ecca3">● Protein (8SDY)</span>
            <span style="color:#e94560;margin-left:15px">● Ligand (Vancomycin) - FIXED</span>
        </div>
    </div>
    <div id="viewport"></div>

    <script>
        let element = document.getElementById('viewport');
        let config = {{ backgroundColor: '#1a1a2e' }};
        let viewer = $3Dmol.createViewer(element, config);
        
        let pdbData = `{pdb_data}`;
        viewer.addModel(pdbData, "pdb");
        
        // Protein in cyan cartoon
        viewer.setStyle({{chain: 'A'}}, {{cartoon: {{color: '#4ecca3', opacity: 0.8}}}});
        
        // Ligand in red sticks/spheres
        viewer.setStyle({{chain: 'B'}}, {{
            stick: {{colorscheme: 'redCarbon', radius: 0.3}}, 
            sphere: {{radius: 0.4}}
        }});
        
        viewer.zoomTo();
        viewer.render();
        
        let spinning = false;
        
        function showSurface() {{
            viewer.addSurface($3Dmol.SurfaceType.VDW, {{opacity: 0.6, color: 'white'}});
            viewer.render();
        }}
        
        function showCartoon() {{
            viewer.removeAllSurfaces();
            viewer.setStyle({{chain: 'A'}}, {{cartoon: {{color: '#4ecca3'}}}});
            viewer.render();
        }}
        
        function showLigand() {{
            viewer.zoomTo({{chain: 'B'}});
            viewer.setStyle({{chain: 'B'}}, {{stick: {{radius: 0.5}}, sphere: {{radius: 0.6}}}});
            viewer.render();
        }}
        
        function showComplex() {{
            viewer.zoomTo();
            viewer.render();
        }}
        
        function resetView() {{
            viewer.removeAllLabels();
            viewer.zoomTo();
            viewer.render();
        }}
        
        function toggleSpin() {{
            spinning = !spinning;
            viewer.spin(spinning ? 'y' : false);
        }}
    </script>
</body>
</html>'''.format(pdb_data=pdb_data)
    
    with open(output_html, 'w') as f:
        f.write(html)
    
    print("HTML viewer created: {}".format(output_html))


def main():
    print("=" * 60)
    print("Creating CORRECT 3D Visualization")
    print("=" * 60)
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Create complex
    complex_pdb = os.path.join(OUTPUT_DIR, "8SDY_Vancomycin_CORRECT.pdb")
    create_complex(PROTEIN_FILE, LIGAND_PDB, complex_pdb)
    
    # Generate HTML
    html_file = os.path.join(OUTPUT_DIR, "viewer_CORRECT.html")
    generate_html_viewer(complex_pdb, html_file)
    
    # Copy files for comparison
    shutil.copy(LIGAND_PDB, os.path.join(OUTPUT_DIR, "Vancomycin_3D.pdb"))
    
    print("\n" + "=" * 60)
    print("CORRECT 3D files created!")
    print("=" * 60)
    print("\nLocation: {}".format(OUTPUT_DIR))
    print("\nFiles:")
    print("  - viewer_CORRECT.html (Open in browser)")
    print("  - 8SDY_Vancomycin_CORRECT.pdb")
    print("  - Vancomycin_3D.pdb")
    
    # Open browser
    print("\nOpening browser...")
    import webbrowser
    webbrowser.open('file:///' + html_file.replace('\\', '/'))


if __name__ == "__main__":
    main()
