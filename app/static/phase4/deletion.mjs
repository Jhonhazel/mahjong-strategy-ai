import { messageFor } from './http.mjs';

// Called only by the explicit confirmation form, never by opening its details.
export function createDeletion({ api, onPending, onSuccess, onError }) {
  let pending = false;
  return async id => {
    if (pending) return false;
    pending = true; onPending(true);
    try {
      await api.deletePrediction(id);
      onSuccess(); return true;
    } catch (error) { onError(messageFor(error)); return false; }
    finally { pending = false; onPending(false); }
  };
}
