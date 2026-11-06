import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
async function client() {
  const url = new URL('../../app/static/phase4/http.mjs', import.meta.url);
  assert.ok(existsSync(url), 'The same-origin HTTP client feature is missing');
  return import(url.href);
}
const json = (value,status=200) => new Response(JSON.stringify(value), { status,headers:{'Content-Type':'application/json'} });
test('mutations send JSON, current CSRF and same-origin cookies with exact turn', async () => {
  const { createHttpClient } = await client(); const requests = [];
  const api = createHttpClient({ csrfToken:'test-token',fetchImpl:async (path,options) => { requests.push({path,options}); return json({ ok:true }); } });
  await api.action('game-id',{ action_id:12,expected_turn_number:4 });
  const { path,options } = requests[0];
  assert.equal(path,'/api/games/game-id/actions'); assert.equal(options.method,'POST');
  assert.equal(options.credentials,'same-origin');
  assert.equal(options.headers['X-CSRF-Token'],'test-token');
  assert.equal(options.headers['Content-Type'],'application/json');
  assert.deepEqual(JSON.parse(options.body),{ action_id:12,expected_turn_number:4 });
});
test('session bootstrap updates in-memory token and no mutation executes without it', async () => {
  const { createHttpClient } = await client(); const requests = [];
  const api = createHttpClient({ fetchImpl:async (path,options) => { requests.push({path,options}); return json({ csrf_token:'t'.repeat(43),expires_in:86400 }); } });
  await assert.rejects(api.createGame({}),error => error.status === 401);
  assert.equal(requests.length,0);
  await api.getSession(); await api.createGame({});
  assert.equal(requests[1].options.headers['X-CSRF-Token'],'t'.repeat(43));
});
test('all required HTTP errors become safe Indonesian messages without backend details', async () => {
  const { createHttpClient } = await client();
  for (const status of [400,401,403,404,409,413,422,429,503]) {
    const api = createHttpClient({ csrfToken:'test',fetchImpl:async () => json({detail:{message:'SELECT secret_password FROM internal'}},status) });
    await assert.rejects(api.getGame('id'),error => error.status === status
      && !error.message.includes('SELECT') && !error.message.includes('secret_password') && error.message.length > 10);
  }
});
test('delete accepts a confirmed204 without JSON and preserves request safety', async () => {
  const { createHttpClient } = await client(); let options;
  const api = createHttpClient({csrfToken:'test',fetchImpl:async (path,request) => { options=request;return new Response(null,{status:204}); }});
  assert.equal(await api.deletePrediction('id'),null);
  assert.equal(options.method,'DELETE');assert.equal(options.credentials,'same-origin');
  assert.equal(options.headers['X-CSRF-Token'],'test');
});
test('network and malformed-success responses fail safely without leaking payload', async () => {
  const { createHttpClient } = await client();
  for (const fetchImpl of [async () => { throw new TypeError('private connection value'); },
    async () => new Response('<script>private</script>',{status:200})]) {
    const api=createHttpClient({fetchImpl});
    await assert.rejects(api.getGame('id'),error => error.status===0 && !error.message.includes('private'));
  }
});
for(const status of [200,201,202])test('delete success '+status+' is not a confirmed204 and must fail safely',async()=>{
  const {createHttpClient}=await client();
  const api=createHttpClient({csrfToken:'test',fetchImpl:async()=>json({ok:true},status)});
  await assert.rejects(api.deletePrediction('id'),error=>error.status===0);
});
