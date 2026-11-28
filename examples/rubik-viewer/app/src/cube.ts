import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { type Colours, FACELETS, FACES, type Move, type Vec, dot } from "./geometry";

const PALETTE: Record<string, number> = {
  White: 0xf4f4f0, Yellow: 0xffd500, Green: 0x009b48, Blue: 0x0046ad, Red: 0xc41e3a, Orange: 0xff5800,
};

/** The cube on screen: 26 cubies on a fixed grid, with stickers coloured from a facelet map.
 *  A turn rotates one layer, then snaps the cubies back home and recolours them. */
export class CubeView {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private cubies: { obj: THREE.Object3D; home: Vec }[] = [];
  private stickers = new Map<string, THREE.MeshStandardMaterial>();
  private dirty = true; // render on demand: only when something moved or changed colour

  constructor(private host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    host.appendChild(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    this.camera.position.set(5.2, 4.4, 7.2);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;

    this.scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.8);
    sun.position.set(4, 8, 6);
    this.scene.add(sun);

    const body = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.6 });
    const box = new THREE.BoxGeometry(0.96, 0.96, 0.96);
    const plate = new THREE.PlaneGeometry(0.82, 0.82);
    const byCubie = new Map<string, THREE.Object3D>();
    for (let x = -1; x <= 1; x++)
      for (let y = -1; y <= 1; y++)
        for (let z = -1; z <= 1; z++) {
          if (!x && !y && !z) continue;
          const obj = new THREE.Group();
          obj.add(new THREE.Mesh(box, body));
          obj.position.set(x, y, z);
          this.scene.add(obj);
          this.cubies.push({ obj, home: [x, y, z] });
          byCubie.set(`${[x, y, z]}`, obj);
        }
    for (const f of FACELETS) {
      const mat = new THREE.MeshStandardMaterial({ color: 0x444444, roughness: 0.35 });
      const sticker = new THREE.Mesh(plate, mat);
      const n = new THREE.Vector3(...f.normal);
      sticker.position.copy(n.clone().multiplyScalar(0.485));
      sticker.lookAt(n.clone().multiplyScalar(2));
      byCubie.get(`${f.cubie}`)!.add(sticker);
      this.stickers.set(f.name, mat);
    }

    new ResizeObserver(() => this.resize()).observe(host);
    this.resize();
    this.controls.addEventListener("change", () => (this.dirty = true));
    const loop = () => {
      this.controls.update(); // keeps damping going; fires "change" while the view moves
      if (this.dirty) {
        this.dirty = false;
        this.renderer.render(this.scene, this.camera);
      }
      requestAnimationFrame(loop);
    };
    loop();
  }

  private resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  paint(colours: Colours) {
    for (const [name, mat] of this.stickers) mat.color.setHex(PALETTE[colours.get(name) ?? ""] ?? 0x444444);
    this.dirty = true;
  }

  /** Animate one move. Resolves when the layer is back on the grid (not yet recoloured). */
  turn(mv: Move, ms: number): Promise<void> {
    const n = FACES[mv.face].n;
    const axis = new THREE.Vector3(...n);
    const angle = mv.quarters === 3 ? Math.PI / 2 : (-Math.PI / 2) * mv.quarters; // clockwise = negative
    const pivot = new THREE.Group();
    this.scene.add(pivot);
    const layer = this.cubies.filter((c) => dot(c.home, n) === 1);
    for (const c of layer) pivot.attach(c.obj);
    const t0 = performance.now();
    const dur = ms * (mv.quarters === 2 ? 1.5 : 1);
    return new Promise((resolve) => {
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / Math.max(1, dur));
        const e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2; // ease in-out
        pivot.setRotationFromAxisAngle(axis, angle * e);
        this.dirty = true;
        if (t < 1) return void requestAnimationFrame(step);
        for (const c of layer) {
          this.scene.attach(c.obj);
          c.obj.position.set(...c.home);
          c.obj.rotation.set(0, 0, 0);
        }
        this.scene.remove(pivot);
        resolve();
      };
      requestAnimationFrame(step);
    });
  }
}
