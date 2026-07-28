import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';

const ASSET_ROOT = '/assets';
const VIEW = window.__PHASE1B_VIEW__ || 'covered-car';

const VIEW_CONFIGS = {
  'covered-car': {
    title: 'V3 · Poly Haven Covered Car',
    subtitle: 'Real 13K-triangle scanned model · 1K local glTF package',
    model: `${ASSET_ROOT}/models/covered_car/covered_car_1k.gltf`,
    floor: 'worn_asphalt',
    rotationY: -0.62,
    cameraBias: [0.95, 0.52, 1.15],
  },
  apartments: {
    title: 'B1 · Modular Urban Apartments Facade',
    subtitle: 'Real 118K-triangle modular facade · 1K local glTF package',
    model: `${ASSET_ROOT}/models/modular_urban_apartments_facade/modular_urban_apartments_facade_1k.gltf`,
    floor: 'concrete_tiles_02',
    rotationY: 0.12,
    cameraBias: [0.88, 0.48, 1.08],
  },
  factory: {
    title: 'B2 · Modular Factory Facade',
    subtitle: 'Real 175K-triangle industrial facade · 1K local glTF package',
    model: `${ASSET_ROOT}/models/modular_factory_facade/modular_factory_facade_1k.gltf`,
    floor: 'worn_asphalt',
    rotationY: -0.08,
    cameraBias: [0.9, 0.5, 1.12],
  },
  materials: {
    title: 'T1–T4 · Approved 2K Photoscanned PBR Materials',
    subtitle: 'Diffuse · OpenGL normal · roughness · AO · displacement',
    materials: [
      ['worn_asphalt', 'T1 · Worn Asphalt'],
      ['concrete_tiles_02', 'T2 · Concrete Tiles 02'],
      ['concrete_layers', 'T3 · Concrete Layers'],
      ['rectangular_facade_tiles_02', 'T4 · Facade Tiles 02'],
    ],
  },
};

function showError(error) {
  console.error(error);
  window.__PHASE1B_ERROR__ = String(error?.stack || error);
  const overlay = document.createElement('div');
  overlay.style.cssText = `position:fixed;inset:0;z-index:99;display:grid;place-items:center;background:#170708;color:#ffd7d7;font:600 18px/1.5 system-ui;padding:48px;text-align:center;white-space:pre-wrap`;
  overlay.textContent = `PHASE 1B HARD FAILURE\n\n${window.__PHASE1B_ERROR__}\n\nNo fallback asset was generated.`;
  document.body.appendChild(overlay);
}

function addUv1(geometry) {
  const uv = geometry.getAttribute('uv');
  if (uv && !geometry.getAttribute('uv1')) geometry.setAttribute('uv1', uv.clone());
}

async function loadPbrMaterial(renderer, name, repeat = [1, 1]) {
  const loader = new THREE.TextureLoader();
  const base = `${ASSET_ROOT}/textures/${name}`;
  const [map, normalMap, roughnessMap, aoMap, displacementMap] = await Promise.all([
    loader.loadAsync(`${base}/diffuse.jpg`),
    loader.loadAsync(`${base}/normal.jpg`),
    loader.loadAsync(`${base}/roughness.jpg`),
    loader.loadAsync(`${base}/ao.jpg`),
    loader.loadAsync(`${base}/displacement.jpg`),
  ]);
  map.colorSpace = THREE.SRGBColorSpace;
  for (const texture of [map, normalMap, roughnessMap, aoMap, displacementMap]) {
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(repeat[0], repeat[1]);
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  }
  return new THREE.MeshStandardMaterial({
    map,
    normalMap,
    roughnessMap,
    aoMap,
    displacementMap,
    displacementScale: name === 'worn_asphalt' ? 0.035 : 0.025,
    roughness: 1,
    metalness: 0,
    envMapIntensity: 0.85,
    normalScale: new THREE.Vector2(0.9, 0.9),
  });
}

async function loadEnvironment(renderer, scene) {
  const hdr = await new RGBELoader().loadAsync(`${ASSET_ROOT}/hdri/urban_street_03_2k.hdr`);
  hdr.mapping = THREE.EquirectangularReflectionMapping;
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  const environment = pmrem.fromEquirectangular(hdr).texture;
  scene.environment = environment;
  scene.background = hdr;
  scene.environmentIntensity = 1.0;
  scene.backgroundIntensity = 0.72;
  scene.backgroundBlurriness = 0.08;
  hdr.dispose();
  pmrem.dispose();
}

function prepareModel(object, rotationY = 0) {
  object.rotation.y = rotationY;
  object.traverse((child) => {
    if (!child.isMesh) return;
    child.castShadow = true;
    child.receiveShadow = true;
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materials) {
      if (!material) continue;
      material.envMapIntensity = Math.max(material.envMapIntensity ?? 0, 1.0);
      if ('roughness' in material) material.roughness = Math.max(0.18, material.roughness ?? 0.7);
      material.needsUpdate = true;
    }
  });

  object.updateMatrixWorld(true);
  let box = new THREE.Box3().setFromObject(object);
  const center = box.getCenter(new THREE.Vector3());
  object.position.x -= center.x;
  object.position.z -= center.z;
  object.position.y -= box.min.y;
  object.updateMatrixWorld(true);
  box = new THREE.Box3().setFromObject(object);
  return { box, size: box.getSize(new THREE.Vector3()) };
}

function fitCamera(camera, size, targetY, bias = [0.9, 0.5, 1.1]) {
  const maxDim = Math.max(size.x, size.y, size.z);
  camera.near = Math.max(0.02, maxDim / 2000);
  camera.far = Math.max(100, maxDim * 20);
  camera.position.set(maxDim * bias[0], Math.max(size.y * 0.58, maxDim * bias[1]), maxDim * bias[2]);
  camera.lookAt(0, targetY, 0);
  camera.updateProjectionMatrix();
}

function createLabel(text) {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 180;
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = 'rgba(5, 10, 16, 0.82)';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = 'rgba(185, 220, 255, 0.65)';
  context.lineWidth = 4;
  context.strokeRect(4, 4, canvas.width - 8, canvas.height - 8);
  context.fillStyle = '#eef7ff';
  context.font = '700 52px system-ui';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(text, canvas.width / 2, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(5.7, 1.0, 1);
  return sprite;
}

function addOverlay(config) {
  const overlay = document.createElement('div');
  overlay.innerHTML = `
    <div class="badge">ACTUAL LOCAL ASSET · GLTFLOADER · NO FALLBACK</div>
    <h1>${config.title}</h1>
    <p>${config.subtitle}</p>
    <div class="facts">
      <span>Lighting: H1 Urban Street 03 HDRI · 2048×1024</span>
      <span>Renderer: ACES Filmic · sRGB · soft shadows</span>
      <span>Failure policy: visible error, never procedural replacement</span>
    </div>`;
  overlay.style.cssText = `position:fixed;z-index:20;left:28px;top:24px;color:#f2f7fb;font-family:Inter,system-ui,sans-serif;text-shadow:0 2px 14px #000;max-width:760px`;
  const style = document.createElement('style');
  style.textContent = `
    html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#05080c}
    canvas{display:block}
    .badge{display:inline-block;padding:7px 10px;border:1px solid rgba(139,211,255,.7);background:rgba(5,18,29,.78);font-size:12px;font-weight:800;letter-spacing:.12em;color:#bfe7ff}
    h1{margin:12px 0 3px;font-size:29px;line-height:1.1;letter-spacing:-.02em}
    p{margin:0 0 11px;color:#d0dbe4;font-size:15px}
    .facts{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#c3d1dc}
    .facts span{width:max-content;max-width:100%;padding:4px 7px;background:rgba(2,7,12,.56);border-left:2px solid rgba(139,211,255,.55)}
  `;
  document.head.appendChild(style);
  document.body.appendChild(overlay);
}

async function buildModelView(renderer, scene, camera, config) {
  const loader = new GLTFLoader();
  const [gltf, floorMaterial] = await Promise.all([
    loader.loadAsync(config.model),
    loadPbrMaterial(renderer, config.floor, [8, 8]),
  ]);
  const model = gltf.scene;
  scene.add(model);
  const { size } = prepareModel(model, config.rotationY);
  const maxDim = Math.max(size.x, size.z, 4);

  const groundGeometry = new THREE.PlaneGeometry(maxDim * 3.6, maxDim * 3.6, 160, 160);
  addUv1(groundGeometry);
  const ground = new THREE.Mesh(groundGeometry, floorMaterial);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.012;
  ground.receiveShadow = true;
  scene.add(ground);

  const targetY = Math.max(size.y * 0.4, 0.65);
  fitCamera(camera, size, targetY, config.cameraBias);
  return model;
}

async function buildMaterialView(renderer, scene, camera, config) {
  const entries = await Promise.all(config.materials.map(async ([name, label]) => ({
    name,
    label,
    material: await loadPbrMaterial(renderer, name, [2.3, 2.3]),
  })));

  const geometry = new THREE.PlaneGeometry(5.5, 5.5, 128, 128);
  addUv1(geometry);
  entries.forEach((entry, index) => {
    const x = index % 2 === 0 ? -3.1 : 3.1;
    const z = index < 2 ? -2.9 : 3.1;
    const mesh = new THREE.Mesh(geometry.clone(), entry.material);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(x, 0, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    const label = createLabel(entry.label);
    label.position.set(x, 1.05, z + 2.0);
    scene.add(label);
  });

  camera.position.set(9.8, 11.5, 13.2);
  camera.lookAt(0, 0, 0);
  camera.near = 0.05;
  camera.far = 100;
  camera.updateProjectionMatrix();
}

async function main() {
  const config = VIEW_CONFIGS[VIEW];
  if (!config) throw new Error(`Unknown Phase 1B approval view: ${VIEW}`);
  addOverlay(config);

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.body.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.05, 500);

  await loadEnvironment(renderer, scene);

  const key = new THREE.DirectionalLight(0xfff3df, 3.6);
  key.position.set(16, 24, 10);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -40;
  key.shadow.camera.right = 40;
  key.shadow.camera.top = 40;
  key.shadow.camera.bottom = -40;
  key.shadow.camera.near = 0.1;
  key.shadow.camera.far = 100;
  key.shadow.bias = -0.00008;
  scene.add(key);

  const fill = new THREE.HemisphereLight(0xc9def1, 0x2c261f, 0.8);
  scene.add(fill);

  if (config.model) await buildModelView(renderer, scene, camera, config);
  else await buildMaterialView(renderer, scene, camera, config);

  await renderer.compileAsync(scene, camera);
  renderer.render(scene, camera);
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  renderer.render(scene, camera);

  window.__PHASE1B_READY__ = true;
  window.__PHASE1B_STATS__ = {
    view: VIEW,
    renderer: renderer.capabilities.isWebGL2 ? 'WebGL2' : 'WebGL1',
    models: config.model ? 1 : 0,
    fallback: false,
  };
}

main().catch(showError);
