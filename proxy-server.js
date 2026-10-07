const http = require('http');
const httpProxy = require('http-proxy');

const STREAMLIT_PORT = 8501;
const PROXY_PORT = 5173;

const { spawn } = require('child_process');
const streamlit = spawn('python3', [
  '-m', 'streamlit', 'run', 'dashboard/app.py',
  '--server.port', String(STREAMLIT_PORT),
  '--server.headless', 'true',
  '--server.address', '0.0.0.0',
], {
  cwd: __dirname,
  env: { ...process.env, PYTHONPATH: __dirname },
  stdio: 'pipe',
});

streamlit.stdout.on('data', (d) => process.stdout.write(`[streamlit] ${d}`));
streamlit.stderr.on('data', (d) => process.stderr.write(`[streamlit] ${d}`));
streamlit.on('exit', (code) => console.log(`Streamlit exited with code ${code}`));

const proxy = httpProxy.createProxyServer({
  target: `http://localhost:${STREAMLIT_PORT}`,
  ws: true,
  changeOrigin: true,
  selfHandleResponse: false,
});

proxy.on('error', (err, req, res) => {
  console.error('Proxy error:', err.message);
  if (res && res.writeHead && !res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('Proxy error');
  }
});

proxy.on('econnreset', (err, req, res) => {
  console.error('ECONNRESET:', err.message);
});

function waitForStreamlit(retries, cb) {
  const req = http.get(`http://localhost:${STREAMLIT_PORT}/`, (res) => {
    res.destroy();
    cb(true);
  });
  req.on('error', () => {
    if (retries > 0) setTimeout(() => waitForStreamlit(retries - 1, cb), 1000);
    else cb(false);
  });
  req.setTimeout(2000, () => {
    req.destroy();
    if (retries > 0) setTimeout(() => waitForStreamlit(retries - 1, cb), 1000);
    else cb(false);
  });
}

waitForStreamlit(30, (ok) => {
  if (!ok) {
    console.error('Streamlit did not start within 30 seconds');
    process.exit(1);
  }
  console.log('Streamlit is up, starting proxy...');

  const server = http.createServer((req, res) => {
    proxy.web(req, res);
  });

  server.on('upgrade', (req, socket, head) => {
    socket.on('error', (e) => console.error('Socket error on upgrade:', e.message));
    proxy.ws(req, socket, head);
  });

  server.listen(PROXY_PORT, '0.0.0.0', () => {
    console.log(`Proxy running on http://0.0.0.0:${PROXY_PORT} -> Streamlit on ${STREAMLIT_PORT}`);
  });
});
