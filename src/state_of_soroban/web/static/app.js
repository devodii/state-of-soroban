const $ = (id) => document.getElementById(id);
const state = { tab: 'repos', page: 0, repo: '' };
let pageSize = 50;
let timer;
let ticket = 0;

const fmt = (n) => (n == null ? '' : Number(n).toLocaleString());
const day = (v) => (v ? String(v).slice(0, 10) : '');
const esc = (s) =>
  String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const gh = (name) => `https://github.com/${name}`;

const columns = {
  repos: ['Repo', 'Stars', 'Forks', '2026 commits', 'Language', 'Pushed'],
  commits: ['Date', 'Repo', 'Author', 'Message', '+/-'],
  issues: ['Date', 'Repo', 'Title', 'State', 'Author', 'Comments'],
  users: ['Contributor', 'Soroban repos', 'Contributions'],
};

const renderers = {
  repos: (r) => `<tr>
    <td><span class="link" data-repo="${esc(r.full_name)}">${esc(r.full_name)}</span>
      ${r.is_soroban ? '<span class="tag soroban">soroban</span>' : ''}
      ${r.is_fork ? `<span class="tag fork">fork of ${esc(r.parent_full_name || '?')}</span>` : ''}
      ${r.archived ? '<span class="tag">archived</span>' : ''}
      <div class="muted">${esc(r.description)}</div></td>
    <td class="num">${fmt(r.stars)}</td><td class="num">${fmt(r.forks)}</td>
    <td class="num">${fmt(r.window_commits)}</td><td>${esc(r.language)}</td><td>${day(r.pushed_at)}</td></tr>`,
  commits: (r) => `<tr>
    <td>${day(r.committed_at)}</td>
    <td><span class="link" data-repo="${esc(r.repo)}">${esc(r.repo)}</span></td>
    <td>${esc(r.author_login)}</td>
    <td><a href="${gh(r.repo)}/commit/${r.sha}" target="_blank">${esc(String(r.message).split('\n')[0].slice(0, 160))}</a>
      ${r.is_fix ? '<span class="tag fix">fix</span>' : ''}</td>
    <td class="num">+${fmt(r.additions)} −${fmt(r.deletions)}</td></tr>`,
  issues: (r) => `<tr>
    <td>${day(r.created_at)}</td>
    <td><span class="link" data-repo="${esc(r.repo)}">${esc(r.repo)}</span></td>
    <td><a href="${esc(r.url)}" target="_blank">${esc(r.title)}</a>
      <span class="tag">${r.kind === 'pull' ? 'PR' : 'issue'}</span>
      ${r.is_bug ? '<span class="tag bug">bug</span>' : ''}</td>
    <td>${esc(r.state)}</td><td>${esc(r.author_login)}</td><td class="num">${fmt(r.comments)}</td></tr>`,
  users: (r) => `<tr>
    <td>${r.avatar_url ? `<img class="av" loading="lazy" src="${esc(r.avatar_url)}&s=48">` : ''}
      <a href="https://github.com/${esc(r.login)}" target="_blank">${esc(r.login)}</a></td>
    <td class="num">${fmt(r.repos)}</td><td class="num">${fmt(r.contributions)}</td></tr>`,
};

function params() {
  const p = new URLSearchParams({ page: state.page, q: $('q').value.trim() });
  if (state.tab === 'repos') {
    p.set('kind', $('kind').value);
    p.set('sort', $('sort').value);
  }
  if (state.repo) p.set('repo', state.repo);
  if ($('fixes').checked) p.set('fixes', 'true');
  if ($('bugs').checked) p.set('bugs', 'true');
  if ($('type').value) p.set('type', $('type').value);
  return p;
}

async function load() {
  const mine = ++ticket;
  const res = await fetch(`/api/${state.tab}?${params()}`);
  const data = await res.json();
  if (mine !== ticket) return;
  $('table').tHead.innerHTML = `<tr>${columns[state.tab].map((c) => `<th>${c}</th>`).join('')}</tr>`;
  $('table').tBodies[0].innerHTML = data.rows.map(renderers[state.tab]).join('');
  pageSize = data.page_size || pageSize;
  const from = state.page * pageSize + 1;
  const to = state.page * pageSize + data.rows.length;
  $('info').textContent = data.rows.length
    ? `${fmt(from)}–${fmt(to)}${data.total != null ? ' of ' + fmt(data.total) : ''}`
    : 'no results';
  $('prev').disabled = state.page === 0;
  $('next').disabled = data.total != null ? to >= data.total : !data.more;
}

function reset() {
  state.page = 0;
  load();
}

function showControls() {
  const t = state.tab;
  $('kind').hidden = $('sort').hidden = t !== 'repos';
  $('fixes-label').hidden = t !== 'commits';
  $('bugs-label').hidden = $('type').hidden = t !== 'issues';
  $('chip').hidden = !state.repo || t === 'repos' || t === 'users';
  $('chip').textContent = `${state.repo} ✕`;
  $('detail').hidden = !state.repo || t === 'users';
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
  showControls();
  reset();
}

async function openRepo(name) {
  state.repo = name;
  const data = await (await fetch(`/api/repo/${name}`)).json();
  const r = data.repo;
  $('detail').innerHTML = `<h2><a href="${gh(r.full_name)}" target="_blank">${esc(r.full_name)}</a>
    ${r.is_soroban ? '<span class="tag soroban">soroban</span>' : ''}
    ${r.is_fork ? `<span class="tag fork">fork of ${esc(r.parent_full_name || '?')}</span>` : ''}</h2>
    <div class="muted">${esc(r.description)}</div>
    <div class="facts">
      <span><b>${fmt(r.stars)}</b> stars</span><span><b>${fmt(r.forks)}</b> forks</span>
      <span><b>${fmt(r.commit_count)}</b> commits (<b>${fmt(r.fix_count)}</b> fixes)</span>
      <span><b>${fmt(r.issue_count)}</b> issues &amp; PRs</span>
      <span><b>${fmt(r.file_count)}</b> files, <b>${fmt(r.function_count)}</b> functions</span>
      <span>networks: ${esc((r.networks || []).join(', ') || 'none seen')}</span>
      <span>found via: ${esc((r.discovered_via || []).slice(0, 4).join(', '))}</span>
    </div>
    <div class="people">${data.contributors
      .map(
        (c) => `<a href="https://github.com/${esc(c.login)}" target="_blank">
        ${c.avatar_url ? `<img class="av" loading="lazy" src="${esc(c.avatar_url)}&s=48">` : ''}${esc(c.login)} · ${fmt(c.contributions)}</a>`,
      )
      .join('')}</div>`;
  if (state.tab === 'repos') state.tab = 'commits';
  setTab(state.tab === 'users' ? 'commits' : state.tab);
}

async function stats() {
  const s = await (await fetch('/api/stats')).json();
  $('stats').innerHTML = Object.entries(s)
    .map(([k, v]) => `<span>${k.replace('_', ' ')} <b>${fmt(v)}</b></span>`)
    .join('');
}

document.querySelectorAll('#tabs button').forEach((b) =>
  b.addEventListener('click', () => {
    if (b.dataset.tab === 'repos') state.repo = '';
    setTab(b.dataset.tab);
  }),
);
$('q').addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(reset, 250);
});
['kind', 'sort', 'fixes', 'bugs', 'type'].forEach((id) => $(id).addEventListener('change', reset));
$('prev').addEventListener('click', () => { state.page--; load(); window.scrollTo(0, 0); });
$('next').addEventListener('click', () => { state.page++; load(); window.scrollTo(0, 0); });
$('chip').addEventListener('click', () => { state.repo = ''; showControls(); reset(); });
$('table').addEventListener('click', (e) => {
  const link = e.target.closest('[data-repo]');
  if (link) openRepo(link.dataset.repo);
});

stats();
setTab('repos');
