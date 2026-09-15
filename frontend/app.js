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
  leaderboardRows: [],
  leaderboardPage: 0,
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
const leaderboardPagination = document.getElementById('leaderboard-pagination');
const leaderboardPrevious = document.getElementById('leaderboard-previous');
const leaderboardNext = document.getElementById('leaderboard-next');
const leaderboardPageStatus = document.getElementById('leaderboard-page-status');
const LEADERBOARD_PAGE_SIZE = 10;

function normalizeApiErrorMessage(detail) {
  if (!detail) {
    return 'Request failed';
  }

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'string' ? item : item?.msg || item?.detail || JSON.stringify(item)))
      .filter(Boolean)
      .join('; ');
  }

  if (typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    if (typeof detail.msg === 'string') return detail.msg;
    if (typeof detail.detail === 'string') return detail.detail;
    if (typeof detail.error === 'string') return detail.error;
    return JSON.stringify(detail);
  }

  return String(detail);
}

async function api(path, options = {}) {
  const { headers: requestHeaders = {}, ...requestOptions } = options;
  const hasBody = requestOptions.body !== undefined && requestOptions.body !== null && requestOptions.body !== '';

  const response = await fetch(`${API_BASE}${path}`, {
    ...requestOptions,
    headers: {
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      ...requestHeaders,
    },
  });

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const message = normalizeApiErrorMessage(data?.detail ?? data);
    throw new Error(message);
  }

  return data;
}

function updateStatus(elementId, message, isError = false) {
  const node = document.getElementById(elementId);
  if (!node) return;

  const renderedMessage = typeof message === 'string'
    ? message
    : message == null
      ? ''
      : typeof message === 'object'
        ? JSON.stringify(message)
        : String(message);

  node.textContent = renderedMessage;
  node.classList.toggle('error', isError);
}

async function ensureSeason() {
  if (state.seasonId) {
    return state.seasonId;
  }

  const season = await api('/seasons/bootstrap', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  state.seasonId = season.id;
  const hiddenSeasonInput = document.getElementById('season-id-input');
  if (hiddenSeasonInput) hiddenSeasonInput.value = String(season.id);
  const seasonNameNode = document.getElementById('season-name');
  if (seasonNameNode) seasonNameNode.textContent = season.name;
  return season.id;
}

async function refreshEliminationOptions() {
  const seasonId = Number(document.getElementById('season-id-input')?.value || state.seasonId || 0);
  if (!eliminationSelect || !state.pairings.length || !seasonId) {
    return;
  }

  try {
    const eliminations = await api(`/seasons/${seasonId}/eliminations`);
    const eliminatedNames = new Set((eliminations || []).map((item) => item.star_name));
    const currentValue = eliminationSelect.value;

    eliminationSelect.innerHTML = '<option value="">Select a pairing</option>';

    const remaining = state.pairings.filter((pairing) => !eliminatedNames.has(pairing.star_name));
    if (remaining.length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No remaining pairings';
      option.disabled = true;
      eliminationSelect.appendChild(option);
      return;
    }

    remaining.forEach((pairing) => {
      const option = document.createElement('option');
      option.value = pairing.star_name;
      option.textContent = `${pairing.star_name} (${pairing.pro_name})`;
      eliminationSelect.appendChild(option);
    });

    if (currentValue && remaining.some((pairing) => pairing.star_name === currentValue)) {
      eliminationSelect.value = currentValue;
    }
  } catch (error) {
    console.error('Unable to refresh elimination options:', error);
  }
}

async function loadPairings() {
  const seasonId = await ensureSeason();
  const pairings = await api(`/seasons/${seasonId}/pairings`);
  state.pairings = pairings;
  state.pool = pairings.map((pairing) => pairing.star_name);
  state.rankings = [];

  await refreshEliminationOptions();

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
      empty.textContent = 'Awaiting selection';
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

function resetPickSheet() {
  if (!state.pairings.length) return;
  const confirmed = window.confirm("Start a new sheet? This will clear your rankings, but won't delete any sheet you've already submitted.");
  if (!confirmed) return;

  state.pool = [...state.pairings.map((pairing) => pairing.star_name)];
  state.rankings = [];
  renderPool();
  renderRankingList();
  updateStatus('pick-status', 'Selection sheet reset. Start over whenever you are ready.');
}

function makePredictionOrder() {
  return [...state.rankings];
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
  const seasonId = document.getElementById('season-id-input')?.value || state.seasonId;
  const starName = eliminationSelect.value;

  if (!starName) {
    updateStatus('elimination-status', 'Pick an eliminated pairing.', true);
    return;
  }

  if (!seasonId) {
    updateStatus('elimination-status', 'No active season is available yet.', true);
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

    const safeStarName = result?.star_name || starName;
    const eliminationNumber = result?.elimination_order ?? 1;
    updateStatus('elimination-status', `${safeStarName} recorded as elimination #${eliminationNumber}.`);

    if (eliminationSelect) {
      eliminationSelect.value = '';
    }

    await refreshLeaderboard();
    await refreshSelectionViewer();
    await refreshEliminationTimeline();
    await refreshEliminationOptions();
  } catch (error) {
    updateStatus('elimination-status', error.message, true);
  }
}

function renderLeaderboard(rows) {
  leaderboardTable.innerHTML = '';
  state.leaderboardRows = rows || [];

  if (state.leaderboardRows.length === 0) {
    leaderboardTable.innerHTML = '<tr><td colspan="4">No scores yet.</td></tr>';
    document.getElementById('current-leader').textContent = 'No picks yet';
    if (leaderboardPagination) leaderboardPagination.classList.add('hidden');
    return;
  }

  const totalPages = Math.ceil(state.leaderboardRows.length / LEADERBOARD_PAGE_SIZE);
  state.leaderboardPage = Math.min(state.leaderboardPage, totalPages - 1);
  const firstRow = state.leaderboardPage * LEADERBOARD_PAGE_SIZE;
  const pageRows = state.leaderboardRows.slice(firstRow, firstRow + LEADERBOARD_PAGE_SIZE);

  pageRows.forEach((entry) => {
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

  const topEntry = state.leaderboardRows[0];
  const tiedLeaders = state.leaderboardRows.filter(
    (entry) => entry.points === topEntry.points && entry.exact === topEntry.exact,
  );
  document.getElementById('current-leader').textContent = tiedLeaders.length === 1
    ? `${topEntry.player_name} (${topEntry.points} pts)`
    : `${tiedLeaders.length} tied for first (${topEntry.points} pts)`;
  document.getElementById('participant-count').textContent = String(state.leaderboardRows.length);

  if (leaderboardPagination) {
    leaderboardPagination.classList.toggle('hidden', totalPages <= 1);
    if (leaderboardPageStatus) {
      const lastRow = Math.min(firstRow + LEADERBOARD_PAGE_SIZE, state.leaderboardRows.length);
      leaderboardPageStatus.textContent = `${firstRow + 1}-${lastRow} of ${state.leaderboardRows.length}`;
    }
    if (leaderboardPrevious) leaderboardPrevious.disabled = state.leaderboardPage === 0;
    if (leaderboardNext) leaderboardNext.disabled = state.leaderboardPage === totalPages - 1;
  }
}

function changeLeaderboardPage(direction) {
  const totalPages = Math.ceil(state.leaderboardRows.length / LEADERBOARD_PAGE_SIZE);
  const nextPage = state.leaderboardPage + direction;
  if (nextPage < 0 || nextPage >= totalPages) return;

  state.leaderboardPage = nextPage;
  renderLeaderboard(state.leaderboardRows);
}

async function refreshLeaderboard() {
  const seasonId = Number(document.getElementById('season-id-input')?.value || state.seasonId || 0);
  if (!seasonId) return;

  try {
    const rows = await api(`/leaderboard/${seasonId}`);
    renderLeaderboard(rows);
    await refreshSelectionViewer();
    await refreshEliminationTimeline();
    await refreshEliminationOptions();
  } catch (error) {
    console.error(error);
  }
}

function getOrdinalSuffix(value) {
  const remainder = value % 10;
  const teen = value % 100;

  if (remainder === 1 && teen !== 11) return 'st';
  if (remainder === 2 && teen !== 12) return 'nd';
  if (remainder === 3 && teen !== 13) return 'rd';
  return 'th';
}

function renderEliminationTimeline(entries) {
  const timeline = document.getElementById('elimination-timeline');
  if (!timeline) return;

  if (!entries || entries.length === 0) {
    timeline.innerHTML = '<p class="status-text">No eliminations recorded yet.</p>';
    return;
  }

  timeline.innerHTML = entries.map((item, index) => {
    const finishPlace = Number(item.place_finished ?? item.elimination_order ?? 0);
    const suffix = getOrdinalSuffix(finishPlace);
    return `
      <div class="timeline-item ${index === 0 ? 'timeline-item--featured' : ''}">
        <div class="timeline-order">${finishPlace}${suffix}</div>
        <div class="timeline-copy">
          <strong>${item.star_name}</strong>
          <span>with ${item.pro_name}</span>
        </div>
      </div>
    `;
  }).join('');
}

async function refreshEliminationTimeline() {
  const seasonId = Number(document.getElementById('season-id-input')?.value || state.seasonId || 0);
  if (!seasonId) return;

  try {
    const items = await api(`/seasons/${seasonId}/eliminations`);
    renderEliminationTimeline(items);
  } catch (error) {
    console.error(error);
    renderEliminationTimeline([]);
  }
}

function renderSelectionViewer(entries) {
  if (!selectionViewer) return;

  if (!entries || entries.length === 0) {
    selectionViewer.innerHTML = '<p class="status-text">No picks submitted yet.</p>';
    return;
  }

  const selectedName = selectionNameSelect?.value;
  if (!selectedName) {
    selectionViewer.innerHTML = '<p class="status-text">Select a participant to view their sheet.</p>';
    return;
  }

  const selectedEntries = entries.filter((entry) => entry.player_name === selectedName);
  if (selectedEntries.length === 0) {
    selectionViewer.innerHTML = '<p class="status-text">No sheet found for this participant.</p>';
    return;
  }

  const cards = selectedEntries.map((entry) => {
    const orderedRows = [...(entry.prediction_rows || entry.predictions.map((starName, index) => ({
      position: index + 1,
      star_name: starName,
      is_eliminated: false,
    })))].sort((left, right) => Number(left.position ?? left.predicted_position ?? 0) - Number(right.position ?? right.predicted_position ?? 0));

    const rows = orderedRows
      .map((row) => {
        const position = Number(row.position ?? row.predicted_position ?? 1);
        const actualOrder = row.elimination_order != null ? Number(row.elimination_order) : null;
        const distance = actualOrder != null ? Math.abs(position - actualOrder) : null;
        const isExact = actualOrder != null && distance === 0;
        const isPartial = actualOrder != null && distance > 0 && distance <= 2;
        const isIncorrect = actualOrder != null && distance > 2;

        const rowClass = isExact
          ? 'selection-row--correct'
          : distance === 1
            ? 'selection-row--partial'
            : distance === 2
              ? 'selection-row--near'
              : isIncorrect
                ? 'selection-row--incorrect'
                : row.is_eliminated
                  ? 'selection-row--eliminated'
                  : '';

        const statusMarkup = isExact
          ? '<span class="selection-status exact">Exact</span>'
          : distance === 1
            ? `<span class="selection-status partial">1 off</span>`
            : distance === 2
              ? `<span class="selection-status near">2 off</span>`
              : isIncorrect
                ? `<span class="selection-status incorrect">${distance} off</span>`
                : row.is_eliminated
                  ? '<span class="selection-status">Out</span>'
                  : '';

        return `
          <li class="selection-row ${rowClass}">
            <span class="selection-rank">${position}</span>
            <span class="selection-name">${row.star_name}</span>
            ${statusMarkup}
          </li>
        `;
      })
      .join('');

    return `
      <div class="selection-card selected">
        <h4>${entry.player_name}</h4>
        <ol>${rows}</ol>
      </div>
    `;
  }).join('');

  selectionViewer.innerHTML = `<div class="selection-cards">${cards}</div>`;
}

async function refreshSelectionViewer() {
  const seasonId = Number(document.getElementById('season-id-input')?.value || state.seasonId || 0);
  if (!seasonId) return;

  try {
    const selections = await api(`/seasons/${seasonId}/pick-sheets`);
    const names = selections.map((entry) => entry.player_name).sort((a, b) => a.localeCompare(b));

    if (selectionNameSelect) {
      const currentValue = selectionNameSelect.value;
      selectionNameSelect.innerHTML = '<option value="">Choose a participant</option>' +
        names.map((name) => `<option value="${name}">${name}</option>`).join('');
      selectionNameSelect.value = names.includes(currentValue) ? currentValue : '';
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
    const hiddenSeasonInput = document.getElementById('season-id-input');
    if (hiddenSeasonInput) hiddenSeasonInput.value = String(seasonId);
    await loadPairings();
    await refreshLeaderboard();
    startCountdown();
  } catch (error) {
    updateStatus('pick-status', error.message, true);
  }
}

document.getElementById('pick-form')?.addEventListener('submit', submitPicks);
document.getElementById('reset-picks-button')?.addEventListener('click', resetPickSheet);
document.getElementById('refresh-leaderboard')?.addEventListener('click', refreshLeaderboard);
leaderboardPrevious?.addEventListener('click', () => changeLeaderboardPage(-1));
leaderboardNext?.addEventListener('click', () => changeLeaderboardPage(1));
document.getElementById('admin-login-form')?.addEventListener('submit', loginAdmin);
document.getElementById('host-message-form')?.addEventListener('submit', updateHostMessage);
document.getElementById('elimination-form')?.addEventListener('submit', recordElimination);
selectionNameSelect?.addEventListener('change', async () => {
  const seasonId = Number(document.getElementById('season-id-input')?.value || state.seasonId || 0);
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
