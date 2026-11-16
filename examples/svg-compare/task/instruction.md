Create a complex, visually impressive 3D scene as a single static SVG file at `/app/scene.svg`.

Requirements:
- Canvas 1200x800 (`width="1200" height="800" viewBox="0 0 1200 800"`).
- It must read convincingly as 3D: use a real perspective (or isometric) projection of 3D geometry, with lighting/shading, depth ordering/occlusion, and shadows or atmospheric depth.
- The scene should be complex: many objects, varied geometry (not just one primitive), and a coherent composition.
- Pure, self-contained SVG: no `<script>`, no `<image>`/raster data, no external references or fonts. Gradients, filters, patterns and clip paths are fine.
- The file must be valid XML and under 5 MB.

You may write and run programs to generate the SVG. Check that the final file meets the requirements before you finish.
