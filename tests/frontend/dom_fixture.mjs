// Small DOM adapter for isolated SVG tests. Native browser behavior is tested separately.
class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.attributes = new Map(); this.children = [];
    this.className = ''; this.disabled = false; this._text = ''; this.parentElement = null;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return name === 'class' ? this.className : this.attributes.get(name) ?? null; }
  append(...children) { for (const child of children) { child.remove(); child.parentElement = this; this.children.push(child); } }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(child => child !== this); this.parentElement = null; }
  replaceChildren(...children) { for (const child of [...this.children]) child.remove(); this._text = ''; this.append(...children); }
  get firstElementChild() { return this.children[0] ?? null; }
  get dataset() { return Object.fromEntries([...this.attributes].filter(([key]) => key.startsWith('data-')).map(([key,value]) => [key.slice(5).replace(/-([a-z])/g, (_,letter) => letter.toUpperCase()),value])); }
  get classList() { return { toggle: (name, force) => { const names = new Set(this.className.split(/\s+/).filter(Boolean)); if (force) names.add(name); else names.delete(name); this.className = [...names].join(' '); } }; }
  querySelectorAll(selector) {
    const matches = (node, part) => {
      const tag = part.match(/^[a-z]+/i)?.[0];
      if (tag && node.tagName !== tag.toUpperCase()) return false;
      for (const [,name] of part.matchAll(/\.([\w-]+)/g)) if (!node.className.split(/\s+/).includes(name)) return false;
      for (const [,name,value] of part.matchAll(/\[([\w-]+)(?:=['"]?([^\]'"\s]+)['"]?)?\]/g)) {
        const actual = node.getAttribute(name); if (actual === null || (value !== undefined && actual !== value)) return false;
      }
      return true;
    };
    return descendants(this).slice(1).filter(node => selector.split(',').some(part => matches(node, part.trim())));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  set textContent(value) { this.replaceChildren(); this._text = String(value); }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
}
export const documentFixture = {
  createElement: tag => new Element(tag),
  createElementNS: (namespace, tag) => new Element(tag),
};
export function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }

export function rendererDocument() {
  const root = new Element('main');
  const ids = ['game-message','game-state','empty-table','new-game','refresh-button','predict-button','submit-action',
    'legal-action','human-hand','claim-actions','game-id','public-state','round-result','hand-hint','table-center',
    'seat-top','seat-left','seat-right','seat-bottom','advisor-availability','prediction'];
  for (const id of ids) { const node = new Element(id === 'new-game' ? 'form' : 'div'); node.setAttribute('id',id); root.append(node); }
  const doc = { ...documentFixture, getElementById: id => descendants(root).find(node => node.getAttribute('id') === id) };
  doc.getElementById('new-game').elements = [];
  return doc;
}
