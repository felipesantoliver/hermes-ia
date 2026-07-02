/* ===================== ESFERAS 3D (INTRO + NÚCLEO NA SIDEBAR) ===================== */
/* Responsabilidade: toda a parte visual em Three.js — a esfera grande da
   tela de introdução (com efeito de explosão) e a mini esfera do menu lateral. */

(function () {
  /* ---------- Esfera da introdução ---------- */
  const canvas = document.getElementById('intro-canvas');
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 1000);
  camera.position.z = 5;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

  const COUNT = 5200;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(COUNT * 3);
  const origins = new Float32Array(COUNT * 3);
  const dirs = new Float32Array(COUNT * 3);

  for (let i = 0; i < COUNT; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(Math.random() * 2 - 1);
    const r = 2;
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);

    positions[i * 3] = x; positions[i * 3 + 1] = y; positions[i * 3 + 2] = z;
    origins[i * 3] = x; origins[i * 3 + 1] = y; origins[i * 3 + 2] = z;

    const len = Math.sqrt(x * x + y * y + z * z);
    dirs[i * 3] = x / len; dirs[i * 3 + 1] = y / len; dirs[i * 3 + 2] = z / len;
  }
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  const material = new THREE.PointsMaterial({
    color: 0x9b59b6, size: 0.028, transparent: true, opacity: 0.95,
    blending: THREE.AdditiveBlending, depthWrite: false
  });
  const points = new THREE.Points(geometry, material);
  scene.add(points);

  let exploding = false;
  let explodeStart = 0;

  function explode() {
    if (exploding) return;
    exploding = true;
    explodeStart = performance.now();
  }

  let raf;
  function animate() {
    raf = requestAnimationFrame(animate);
    points.rotation.y += exploding ? 0.012 : 0.0028;
    points.rotation.x += 0.0006;

    if (exploding) {
      const elapsed = (performance.now() - explodeStart) / 1000;
      const pos = geometry.attributes.position.array;
      const ease = Math.min(elapsed / 1.3, 1);
      const push = ease * ease * 14;

      for (let i = 0; i < COUNT; i++) {
        pos[i * 3] = origins[i * 3] + dirs[i * 3] * push;
        pos[i * 3 + 1] = origins[i * 3 + 1] + dirs[i * 3 + 1] * push;
        pos[i * 3 + 2] = origins[i * 3 + 2] + dirs[i * 3 + 2] * push;
      }
      geometry.attributes.position.needsUpdate = true;
      material.opacity = Math.max(0, 0.95 * (1 - ease * 1.15));
    }
    renderer.render(scene, camera);
  }
  animate();

  window.addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });

  const introEl = document.getElementById('intro');
  const appEl = document.getElementById('app');

  function finishIntro() {
    explode();
    setTimeout(() => {
      introEl.classList.add('fade-out');
      appEl.classList.add('visible');
      setTimeout(() => {
        introEl.style.display = 'none';
        cancelAnimationFrame(raf);
      }, 1200);
    }, 900);
  }

  introEl.addEventListener('click', finishIntro);
  setTimeout(finishIntro, 3200);

  /* ---------- Mini esfera da sidebar ---------- */
  const miniCanvas = document.getElementById('mini-sphere-canvas');
  const miniScene = new THREE.Scene();
  const miniCamera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  miniCamera.position.z = 4;

  const miniRenderer = new THREE.WebGLRenderer({ canvas: miniCanvas, antialias: true, alpha: true });
  miniRenderer.setSize(64, 64, false);
  miniRenderer.setPixelRatio(Math.min(devicePixelRatio, 2));

  const MINI_COUNT = 900;
  const miniGeometry = new THREE.BufferGeometry();
  const miniPositions = new Float32Array(MINI_COUNT * 3);

  for (let i = 0; i < MINI_COUNT; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(Math.random() * 2 - 1);
    const r = 1.6;
    miniPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    miniPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    miniPositions[i * 3 + 2] = r * Math.cos(phi);
  }
  miniGeometry.setAttribute('position', new THREE.BufferAttribute(miniPositions, 3));

  const miniMaterial = new THREE.PointsMaterial({
    color: 0x9b59b6, size: 0.045, transparent: true, opacity: 0.9,
    blending: THREE.AdditiveBlending, depthWrite: false
  });
  const miniPoints = new THREE.Points(miniGeometry, miniMaterial);
  miniScene.add(miniPoints);

  // Velocidade da mini esfera: acelera enquanto o usuário digita no chat
  let miniSpeed = 0.004;

  // ---------- Pulso reativo durante geração de resposta ----------
  // A geometria da mini esfera é uma nuvem de pontos (THREE.Points), não uma
  // malha sólida com material emissivo — por isso o "pulso" é aplicado via
  // escala do objeto (miniPoints.scale) e, como aproximação de brilho, via
  // opacidade do PointsMaterial (não há emissive em PointsMaterial).
  const PULSE_SPEED = 1.1;       // "frequência" do pulso (osciladas por segundo, aprox.)
  const PULSE_AMPLITUDE = 0.06;  // escala oscila entre 1 - 0.06 e 1 + 0.06 (0.94 a 1.06)
  const BASE_OPACITY = 0.9;
  const GLOW_AMPLITUDE = 0.08;

  let isGenerating = false;
  let currentScale = 1;
  let pulseElapsed = 0;
  let lastMiniFrameTime = performance.now();

  function setGenerating(value) {
    isGenerating = !!value;
  }

  function animateMini() {
    requestAnimationFrame(animateMini);
    miniPoints.rotation.y += miniSpeed;
    miniPoints.rotation.x += miniSpeed * 0.3;

    const now = performance.now();
    const dt = Math.min((now - lastMiniFrameTime) / 1000, 0.1); // clamp p/ evitar saltos (aba em background etc.)
    lastMiniFrameTime = now;

    if (isGenerating) {
      pulseElapsed += dt;
      const wave = Math.sin(pulseElapsed * PULSE_SPEED * Math.PI * 2); // -1..1
      const targetScale = 1 + wave * PULSE_AMPLITUDE;
      // Segue o alvo do pulso suavemente (não é um salto abrupto entre frames)
      currentScale += (targetScale - currentScale) * Math.min(1, dt * 14);
      miniMaterial.opacity = BASE_OPACITY + wave * GLOW_AMPLITUDE;
    } else {
      // Ao voltar de isGenerating=true, interpola suavemente de volta a 1.0
      // em vez de resetar abruptamente.
      currentScale += (1 - currentScale) * Math.min(1, dt * 8);
      miniMaterial.opacity += (BASE_OPACITY - miniMaterial.opacity) * Math.min(1, dt * 8);
      pulseElapsed = 0;
    }

    miniPoints.scale.setScalar(currentScale);
    miniRenderer.render(miniScene, miniCamera);
  }
  animateMini();

  window.HermesSphere = { setGenerating };

  const wrap = document.getElementById('mini-sphere-wrap');
  wrap.addEventListener('click', () => {
    miniCanvas.classList.remove('pulse');
    void miniCanvas.offsetWidth; // reinicia a animação CSS
    miniCanvas.classList.add('pulse');
  });

  const input = document.getElementById('msg-input');
  let typingTimeout;
  input.addEventListener('input', () => {
    miniSpeed = 0.02;
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => { miniSpeed = 0.004; }, 500);
  });
})();