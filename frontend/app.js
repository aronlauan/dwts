const DEFAULT_LOCAL_API_BASE = 'http://127.0.0.1:8000';
const API_BASE = window.__DWTS_API_BASE__ ||
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? DEFAULT_LOCAL_API_BASE
    : window.location.origin);
const ADMIN_KEY = 'dwts-admin-dev-key';

const state = {
  seasonId: null,
  pairings: [],
  userId: null,
  adminKey: null,
  pool: [],
  rankings: [],
  draggedStar: null,
  deadline: new Date('2026-09-15T20:00:00-05:00'),
  hostMessage: '',
};

function setAdminControlsVisible(isVisible) {
  const controls = document.getElementById('admin-controls');
  if (!controls) return;
  controls.classList.toggle('hidden', !isVisible);
}

function setAdminPanelVisible(isVisible) {
  const panel = document.getElementById('admin-panel');
  if (!panel) return;
  panel.classList.toggle('hidden', !isVisible);
}

const leaderboardTable = document.getElementById('leaderboard-body');
const pairingPool = document.getElementById('pairing-pool');
const rankedPairs = document.getElementById('ranked-pairs');
const eliminationSelect = document.getElementById('elimination-select');
const selectionNameSelect = document.getElementById('selection-name-select');
const selectionViewer = document.getElementById('selection-viewer');

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const message = data?.detail || 'Request failed';
    throw new Error(message);
  }

  return data;
}

function updateStatus(elementId, message, isError = false) {
  const node = document.getElementById(elementId);
  if (!node) return;
  node.textContent = message;
  node.classList.toggle('error', isError);
}

async function ensureSeason() {
  if (state.seasonId) {
    return state.seasonId;
  }

  const season = await api('/seasons/bootstrap', { method: 'POST' });
  state.seasonId = season.id;
  document.getElementById('season-id-input').value = season.id;
  document.getElementById('season-name').textContent = season.name;
  return season.id;
}

async function loadPairings() {
  const seasonId = await ensureSeason();
  const pairings = await api(`/seasons/${seasonId}/pairings`);
  state.pairings = pairings;
  state.pool = pairings.map((pairing) => pairing.star_name);
  state.rankings = [];

  eliminationSelect.innerHTML = '<option value="">Select a pairing</option>';

  pairings.forEach((pairing) => {
    const option = document.createElement('option');
    option.value = pairing.star_name;
    option.textContent = `${pairing.star_name} (${pairing.pro_name})`;
    eliminationSelect.appendChild(option);
  });

  renderPool();
  renderRankingList();
}

function renderPool() {
  pairingPool.innerHTML = '';

  if (state.pool.length === 0) {
    pairingPool.innerHTML = '<div class="rank-slot-empty">All pairings have been ranked.</div>';
    return;
  }

  state.pool.forEach((starName) => {
    const pairing = state.pairings.find((entry) => entry.star_name === starName);
    const card = document.createElement('div');
    card.className = 'drag-card';
    card.draggable = true;
    card.dataset.starName = starName;
    card.innerHTML = `
      <div class="drag-card-name">
        <strong>${starName}</strong>
        <small>with ${pairing ? pairing.pro_name : 'pro'}</small>
      </div>
      <span class="drag-card-tag"></span>
    `;

    card.addEventListener('dragstart', (event) => {
      state.draggedStar = starName;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', starName);
    });

    card.addEventListener('dragend', () => {
      state.draggedStar = null;
      document.querySelectorAll('.rank-slot').forEach((slot) => slot.classList.remove('drag-over'));
    });

    card.addEventListener('click', () => {
      moveStarToRanking(starName, state.rankings.length);
    });

    pairingPool.appendChild(card);
  });
}

function getSlotLabel(position) {
  const remainder = position % 10;
  const teens = position % 100;
  let suffix = 'th';

  if (remainder === 1 && teens !== 11) suffix = 'st';
  else if (remainder === 2 && teens !== 12) suffix = 'nd';
  else if (remainder === 3 && teens !== 13) suffix = 'rd';

  return `${position}${suffix}`;
}

function renderRankingList() {
  rankedPairs.innerHTML = '';

  const slots = Array.from({ length: state.pairings.length }, (_, index) => index);

  slots.forEach((slotIndex) => {
    const slot = document.createElement('div');
    slot.className = 'rank-slot';
    slot.dataset.index = String(slotIndex);

    const label = document.createElement('div');
    label.className = 'rank-slot-index';
    if (slotIndex === 0) {
      label.classList.add('winner-badge');
      label.textContent = '👑';
    } else {
      label.textContent = getSlotLabel(slotIndex + 1);
    }
    slot.appendChild(label);

    const placedName = state.rankings[slotIndex];
    if (!placedName) {
      const empty = document.createElement('div');
      empty.className = 'rank-slot-empty';
      empty.textContent = 'Drop pairing here';
      slot.appendChild(empty);
    } else {
      const pairing = state.pairings.find((entry) => entry.star_name === placedName);
      const card = document.createElement('div');
      card.className = 'drag-card';
      card.draggable = true;
      card.dataset.starName = placedName;
      card.innerHTML = `
        <div class="drag-card-name">
          <strong>${placedName}</strong>
          <small>with ${pairing ? pairing.pro_name : 'pro'}</small>
        </div>
        <span class="drag-card-tag"></span>
      `;

      card.addEventListener('dragstart', (event) => {
        state.draggedStar = placedName;
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', placedName);
      });

      card.addEventListener('dragend', () => {
        state.draggedStar = null;
        document.querySelectorAll('.rank-slot').forEach((element) => element.classList.remove('drag-over'));
      });

      card.addEventListener('click', () => {
        moveStarToPool(placedName);
      });

      slot.appendChild(card);
    }

    slot.addEventListener('dragover', (event) => {
      event.preventDefault();
      slot.classList.add('drag-over');
    });

    slot.addEventListener('dragleave', () => {
      slot.classList.remove('drag-over');
    });

    slot.addEventListener('drop', (event) => {
      event.preventDefault();
      slot.classList.remove('drag-over');
      const targetIndex = Number(slot.dataset.index);
      const draggedName = event.dataTransfer.getData('text/plain') || state.draggedStar;
      if (!draggedName) return;
      moveStarToRanking(draggedName, targetIndex);
    });

    rankedPairs.appendChild(slot);
  });
}

function moveStarToRanking(starName, targetIndex) {
  if (!starName) return;

  state.pool = state.pool.filter((name) => name !== starName);
  state.rankings = state.rankings.filter((name) => name !== starName);

  const insertAt = Math.min(Math.max(targetIndex, 0), state.pairings.length - 1);
  const nextRankings = [...state.rankings];
  nextRankings.splice(insertAt, 0, starName);
  state.rankings = nextRankings.slice(0, state.pairings.length);

  renderPool();
  renderRankingList();
}

function moveStarToPool(starName) {
  if (!starName) return;
  state.rankings = state.rankings.filter((name) => name !== starName);
  if (!state.pool.includes(starName)) {
    state.pool.push(starName);
  }
  renderPool();
  renderRankingList();
}

function makePredictionOrder() {
  return [...state.rankings].reverse();
}

async function loginAdmin(event) {
  event.preventDefault();
  const username = document.getElementById('admin-username-input').value.trim();
  const password = document.getElementById('admin-password-input').value;

  if (!username || !password) {
    updateStatus('admin-login-status', 'Please enter admin username and password.', true);
    return;
  }

  try {
    const data = await api('/admin/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    state.adminKey = data.admin_key;
    updateStatus('admin-login-status', `Admin access enabled for ${data.username}.`);
    setAdminControlsVisible(true);
    const hostMessageForm = document.getElementById('host-message-form');
    if (hostMessageForm) hostMessageForm.classList.remove('hidden');
    await loadPairings();
  } catch (error) {
    updateStatus('admin-login-status', error.message, true);
    setAdminControlsVisible(false);
  }
}

function updateCountdown() {
  const countdown = document.getElementById('countdown-text');
  const daysNode = document.getElementById('countdown-days');
  const hoursNode = document.getElementById('countdown-hours');
  const minutesNode = document.getElementById('countdown-minutes');
  const secondsNode = document.getElementById('countdown-seconds');

  if (!countdown) return;

  const difference = state.deadline.getTime() - Date.now();
  if (difference <= 0) {
    countdown.textContent = 'Selections locked — Tuesday, September 15 at 8:00 PM EST';
    if (daysNode) daysNode.textContent = '00';
    if (hoursNode) hoursNode.textContent = '00';
    if (minutesNode) minutesNode.textContent = '00';
    if (secondsNode) secondsNode.textContent = '00';
    const submitButton = document.querySelector('#pick-form button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    return;
  }

  const days = Math.floor(difference / (1000 * 60 * 60 * 24));
  const hours = Math.floor((difference / (1000 * 60 * 60)) % 24);
  const minutes = Math.floor((difference / (1000 * 60)) % 60);
  const seconds = Math.floor((difference / 1000) % 60);

  if (daysNode) daysNode.textContent = String(days).padStart(2, '0');
  if (hoursNode) hoursNode.textContent = String(hours).padStart(2, '0');
  if (minutesNode) minutesNode.textContent = String(minutes).padStart(2, '0');
  if (secondsNode) secondsNode.textContent = String(seconds).padStart(2, '0');

  countdown.textContent = 'Locking before Tuesday, September 15 at 8:00 PM EST';
}

function startCountdown() {
  updateCountdown();
  window.setInterval(updateCountdown, 1000);
}

async function submitPicks(event) {
  event.preventDefault();
  const seasonId = document.getElementById('season-id-input').value || state.seasonId;
  const playerName = document.getElementById('player-name-input').value.trim();

  if (!seasonId || !playerName) {
    updateStatus('pick-status', 'Please enter your name and make sure the season is set.', true);
    return;
  }

  if (Date.now() >= state.deadline.getTime()) {
    updateStatus('pick-status', 'Selections are locked. The deadline has passed.', true);
    return;
  }

  const predictions = makePredictionOrder();
  if (predictions.length !== state.pairings.length) {
    updateStatus('pick-status', 'Choose a full ordering for every pairing.', true);
    return;
  }

  try {
    await api('/pick-sheets', {
      method: 'POST',
      body: JSON.stringify({
        name: playerName,
        season_id: Number(seasonId),
        predictions,
      }),
    });
    updateStatus('pick-status', 'Pick sheet submitted successfully.');
    await refreshLeaderboard();
  } catch (error) {
    updateStatus('pick-status', error.message, true);
  }
}

async function recordElimination(event) {
  event.preventDefault();
  const seasonId = document.getElementById('season-id-input').value || state.seasonId;
  const starName = eliminationSelect.value;

  if (!seasonId || !starName) {
    updateStatus('elimination-status', 'Pick a season and eliminated pairing.', true);
    return;
  }

  try {
    const adminKey = state.adminKey || ADMIN_KEY;
    const result = await api('/eliminations', {
      method: 'POST',
      headers: {
        'X-Admin-Key': adminKey,
      },
      body: JSON.stringify({
        season_id: Number(seasonId),
        star_name: starName,
      }),
    });
    updateStatus('elimination-status', `${result.star_name} recorded as elimination #${result.elimination_order}.`);
    await refreshLeaderboard();
  } catch (error) {
    updateStatus('elimination-status', error.message, true);
  }
}

function renderLeaderboard(rows) {
  leaderboardTable.innerHTML = '';

  if (!rows || rows.length === 0) {
    leaderboardTable.innerHTML = '<tr><td colspan="4">No scores yet.</td></tr>';
    document.getElementById('current-leader').textContent = 'No picks yet';
    return;
  }

  rows.forEach((entry) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="rank-pill">${entry.rank}</span></td>
      <td>
        <div class="player-cell">
          <div class="avatar">${(entry.player_name || 'P').charAt(0).toUpperCase()}</div>
          <span>${entry.player_name}</span>
        </div>
      </td>
      <td>${entry.points}</td>
      <td>${entry.exact}</td>
    `;
    leaderboardTable.appendChild(tr);
  });

  document.getElementById('current-leader').textContent = `${rows[0].player_name} (${rows[0].points} pts)`;
  document.getElementById('participant-count').textContent = String(rows.length);
}

async function refreshLeaderboard() {
  const seasonId = document.getElementById('season-id-input').value || state.seasonId;
  if (!seasonId) return;

  try {
    const rows = await api(`/leaderboard/${seasonId}`);
    renderLeaderboard(rows);
    await refreshSelectionViewer();
  } catch (error) {
    console.error(error);
  }
}

function renderSelectionViewer(entries) {
  if (!selectionViewer) return;
  if (!entries || entries.length === 0) {
    selectionViewer.innerHTML = '<p class="status-text">No picks submitted yet.</p>';
    return;
  }

  const selectedName = selectionNameSelect?.value;
  const selection = selectedName
    ? entries.find((entry) => entry.player_name === selectedName)
    : entries[0];

  if (!selection) {
    selectionViewer.innerHTML = '<p class="status-text">No selection available for that name.</p>';
    return;
  }

  const picks = selection.predictions.map((starName, index) => `
    <li class="selection-row">
      <span class="selection-rank">${index + 1}</span>
      <span>${starName}</span>
    </li>
  `).join('');

  selectionViewer.innerHTML = `
    <div class="selection-card">
      <h4>${selection.player_name}</h4>
      <ol>${picks}</ol>
    </div>
  `;
}

async function refreshSelectionViewer() {
  const seasonId = document.getElementById('season-id-input').value || state.seasonId;
  if (!seasonId) return;

  try {
    const selections = await api(`/seasons/${seasonId}/pick-sheets`);
    const names = selections.map((entry) => entry.player_name).sort((a, b) => a.localeCompare(b));

    if (selectionNameSelect) {
      const currentValue = selectionNameSelect.value;
      selectionNameSelect.innerHTML = '<option value="">Choose a participant</option>' +
        names.map((name) => `<option value="${name}">${name}</option>`).join('');
      selectionNameSelect.value = names.includes(currentValue) ? currentValue : (names[0] || '');
    }

    renderSelectionViewer(selections);
  } catch (error) {
    console.error(error);
  }
}

async function loadHostMessage() {
  try {
    const data = await api('/site-message');
    state.hostMessage = data.message || 'Keep it glam, keep it bold, and bring your best picks.';
    const hostMessageText = document.getElementById('host-message-text');
    const hostMessageInput = document.getElementById('host-message-input');
    if (hostMessageText) hostMessageText.textContent = state.hostMessage;
    if (hostMessageInput) hostMessageInput.value = state.hostMessage;
  } catch (error) {
    console.error('Unable to load host message:', error);
  }
}

async function updateHostMessage(event) {
  event.preventDefault();
  const textarea = document.getElementById('host-message-input');
  const message = textarea?.value.trim();

  if (!message) {
    updateStatus('admin-login-status', 'Please enter a message for the host update.', true);
    return;
  }

  try {
    const data = await api('/site-message', {
      method: 'POST',
      headers: {
        'X-Admin-Key': state.adminKey || ADMIN_KEY,
      },
      body: JSON.stringify({ message }),
    });

    state.hostMessage = data.message;
    const hostMessageText = document.getElementById('host-message-text');
    if (hostMessageText) hostMessageText.textContent = data.message;
    textarea.value = data.message;
    updateStatus('admin-login-status', 'Host message updated successfully.');
  } catch (error) {
    updateStatus('admin-login-status', error.message, true);
  }
}

async function init() {
  try {
    await loadHostMessage();
    const seasonId = await ensureSeason();
    document.getElementById('season-id-input').value = seasonId;
    await loadPairings();
    await refreshLeaderboard();
    startCountdown();
  } catch (error) {
    updateStatus('pick-status', error.message, true);
  }
}

document.getElementById('pick-form')?.addEventListener('submit', submitPicks);
document.getElementById('refresh-leaderboard')?.addEventListener('click', refreshLeaderboard);
document.getElementById('admin-login-form')?.addEventListener('submit', loginAdmin);
document.getElementById('host-message-form')?.addEventListener('submit', updateHostMessage);
document.getElementById('elimination-form')?.addEventListener('submit', recordElimination);
selectionNameSelect?.addEventListener('change', async () => {
  const seasonId = document.getElementById('season-id-input').value || state.seasonId;
  if (!seasonId) return;
  try {
    const selections = await api(`/seasons/${seasonId}/pick-sheets`);
    renderSelectionViewer(selections);
  } catch (error) {
    console.error(error);
  }
});

setAdminControlsVisible(false);

init();
