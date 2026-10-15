# Kings Wood Viewer — Zoom Controls

The original `public/recon-live.html` is included in the v0.4 download package with integrated zoom.

The reusable `public/zoom-controls.js` supports:

- 50–300% camera zoom, slider and percentage readout
- Mouse wheel zoom focused on the scene
- Pointer Events: touchscreen pinch to zoom and drag to orbit
- Keyboard: +, -, 0 (reset); scene focus required
- Programmatic zoomIn, zoomOut, reset, setZoom
- Bounds and ARIA slider values

The controls transform **illustrative 2.5D artwork**, not measured aerial imagery.

Integration on another HTML viewer:

```html
<script src="/zoom-controls.js"></script>
<script>
 const controls = AeroZoom.attach({
   scene: document.getElementById('scene'),
   building: document.getElementById('building'),
   slider: document.getElementById('zoom'),
   readout: document.getElementById('zoomReadout'),
   orbitToggle: enabled => { /* pause or resume auto-orbit */ }
 });
 document.getElementById('zoomIn').onclick = controls.zoomIn;
 document.getElementById('zoomOut').onclick = controls.zoomOut;
</script>
```
