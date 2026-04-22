// Three.js audio-reactive particle background
let scene, camera, renderer, particles, clock;
let mouseX = 0, mouseY = 0;
let energy = 0; // 0-1, driven by job activity

export function initVisualizer() {
  const canvas = document.getElementById('three-bg');
  if (!canvas || !window.THREE) return;

  const THREE = window.THREE;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 3;

  renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  clock = new THREE.Clock();

  // Particle system
  const count = 800;
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 8;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 8;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 8;
    // Purple-blue gradient
    colors[i * 3] = 0.4 + Math.random() * 0.2;
    colors[i * 3 + 1] = 0.35 + Math.random() * 0.15;
    colors[i * 3 + 2] = 0.8 + Math.random() * 0.2;
    sizes[i] = Math.random() * 3 + 1;
  }

  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  const mat = new THREE.PointsMaterial({
    size: 0.02,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
  });

  particles = new THREE.Points(geo, mat);
  scene.add(particles);

  // Mouse tracking
  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  animate();
}

function animate() {
  requestAnimationFrame(animate);
  if (!particles) return;

  const t = clock.getElapsedTime();
  const pos = particles.geometry.attributes.position.array;

  for (let i = 0; i < pos.length; i += 3) {
    // Gentle wave + energy pulse
    pos[i + 1] += Math.sin(t * 0.5 + pos[i] * 0.5) * 0.001;
    pos[i] += Math.cos(t * 0.3 + pos[i + 2]) * 0.0005;

    // Energy burst when processing
    if (energy > 0) {
      pos[i] += Math.sin(t * 3 + i) * energy * 0.003;
      pos[i + 1] += Math.cos(t * 2 + i) * energy * 0.003;
    }
  }

  particles.geometry.attributes.position.needsUpdate = true;
  particles.rotation.y = t * 0.05 + mouseX * 0.1;
  particles.rotation.x = mouseY * 0.05;
  particles.material.opacity = 0.3 + energy * 0.4;

  // Decay energy
  energy *= 0.98;

  renderer.render(scene, camera);
}

export function setEnergy(val) {
  energy = Math.min(1, Math.max(0, val));
}

export function pulse() {
  energy = 1;
}
