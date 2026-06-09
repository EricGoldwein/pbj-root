const D3_SCRIPT = 'https://d3js.org/d3.v7.min.js';
const TOPOJSON_SCRIPT = 'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js';

type MapLibs = {
  d3: Record<string, unknown> | null;
  topojson: { feature: (...args: unknown[]) => unknown } | null;
};

function waitForGlobal(name: 'd3' | 'topojson', timeoutMs = 4000): Promise<boolean> {
  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      if ((window as unknown as Record<string, unknown>)[name]) {
        resolve(true);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(false);
        return;
      }
      window.setTimeout(tick, 50);
    };
    tick();
  });
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

/** Load D3 + topojson-client for US map outlines (decorative). */
export async function loadMapLibraries(): Promise<MapLibs> {
  try {
    await Promise.all([loadScript(D3_SCRIPT), loadScript(TOPOJSON_SCRIPT)]);
    const [hasD3, hasTopojson] = await Promise.all([
      waitForGlobal('d3'),
      waitForGlobal('topojson'),
    ]);
    const w = window as unknown as MapLibs;
    if (!hasD3 || !hasTopojson || !w.d3 || !w.topojson) {
      return { d3: null, topojson: null };
    }
    return { d3: w.d3, topojson: w.topojson };
  } catch {
    return { d3: null, topojson: null };
  }
}
