// Public captured API data for unit contracts; fake timelines are not gameplay evidence.
import { readFileSync } from 'node:fs';
const actual = JSON.parse(readFileSync(new URL('../../artifacts/phase3/api_examples.json', import.meta.url), 'utf8'));
export function view(changes = {}) { return { ...structuredClone(actual.game_response), ...changes }; }
export function prediction(changes = {}) {
  return { ...structuredClone(actual.prediction_response), ...changes };
}
export function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
export function fakeApi(options = {}) {
  const requests = [];
  const api = { requests };
  for (const name of ['createGame', 'getGame', 'action', 'predict']) {
    api[name] = async (...args) => {
      requests.push({ name, args });
      if (options[name]) return options[name](...args);
      if (name === 'predict') return prediction();
      return view(name === 'action' ? { turn_number: 20 } : {});
    };
  }
  return api;
}
