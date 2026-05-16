(() => {
  "use strict";

  const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const DIRECTIONS = {
    w: [[-1, 0], [0, -1], [0, 1]],
    b: [[1, 0], [0, -1], [0, 1]],
    king: [[-1, 0], [1, 0], [0, -1], [0, 1]],
  };
  const PIECE_VALUE = { man: 100, king: 260 };
  const PLAYER_NAME = window.DAMA_ARENA?.playerName || "Sen";
  const SCORE_URL = window.DAMA_ARENA?.scoreUrl || "/api/oyun/puan";
  const SCORE_ENABLED = Boolean(window.DAMA_ARENA?.scoreEnabled);

  let game;
  const els = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    els.board = document.getElementById("damaBoard");
    els.statusCard = document.getElementById("statusCard");
    els.statusTitle = document.getElementById("statusTitle");
    els.statusText = document.getElementById("statusText");
    els.moveCount = document.getElementById("moveCount");
    els.xpBadge = document.getElementById("xpBadge");
    els.takenWhite = document.getElementById("takenWhite");
    els.takenBlack = document.getElementById("takenBlack");
    els.moveHistory = document.getElementById("moveHistory");
    els.notice = document.getElementById("notice");
    els.modeAi = document.getElementById("modeAi");
    els.modeLocal = document.getElementById("modeLocal");
    els.difficulty = document.getElementById("difficulty");
    els.newGame = document.getElementById("newGameBtn");
    els.flip = document.getElementById("flipBtn");
    els.whitePlayer = document.getElementById("whitePlayer");
    els.blackPlayer = document.getElementById("blackPlayer");

    els.modeAi.addEventListener("click", () => resetGame("ai"));
    els.modeLocal.addEventListener("click", () => resetGame("local"));
    els.newGame.addEventListener("click", () => resetGame(game?.mode || "ai"));
    els.flip.addEventListener("click", () => {
      game.orientation = game.orientation === "w" ? "b" : "w";
      renderBoard();
    });
    els.difficulty.addEventListener("change", () => {
      if (game) game.difficulty = els.difficulty.value;
    });

    resetGame("ai");
  }

  function resetGame(mode) {
    game = {
      board: initialBoard(),
      turn: "w",
      mode,
      aiColor: "b",
      orientation: game?.orientation || "w",
      difficulty: els.difficulty.value,
      selected: null,
      legal: [],
      lastMove: null,
      takenBy: { w: [], b: [] },
      history: [],
      status: "playing",
      winner: null,
      thinking: false,
      busy: false,
      resultSaved: false,
    };
    els.notice.textContent = "";
    renderAll();
  }

  function initialBoard() {
    const board = Array.from({ length: 8 }, () => Array(8).fill(null));
    for (let c = 0; c < 8; c += 1) {
      board[1][c] = { c: "b", k: false };
      board[2][c] = { c: "b", k: false };
      board[5][c] = { c: "w", k: false };
      board[6][c] = { c: "w", k: false };
    }
    return board;
  }

  function renderAll() {
    renderBoard();
    renderStatus();
    renderTaken();
    renderMoves();
    renderControls();
  }

  function renderBoard() {
    els.board.innerHTML = "";
    for (let displayR = 0; displayR < 8; displayR += 1) {
      for (let displayC = 0; displayC < 8; displayC += 1) {
        const { r, c } = displayToBoard(displayR, displayC);
        const piece = game.board[r][c];
        const square = document.createElement("button");
        const isSelected = game.selected && game.selected.r === r && game.selected.c === c;
        const legalMove = game.legal.find((move) => move.to.r === r && move.to.c === c);
        const isLastFrom = game.lastMove && game.lastMove.from.r === r && game.lastMove.from.c === c;
        const isLastTo = game.lastMove && game.lastMove.to.r === r && game.lastMove.to.c === c;

        square.type = "button";
        square.className = [
          "square",
          (r + c) % 2 === 0 ? "light" : "dark",
          isSelected ? "selected" : "",
          legalMove ? "legal" : "",
          legalMove && legalMove.captures.length ? "capture" : "",
          isLastFrom ? "last-from" : "",
          isLastTo ? "last-to" : "",
        ].filter(Boolean).join(" ");
        square.dataset.r = String(r);
        square.dataset.c = String(c);
        square.setAttribute("aria-label", `${coordName(r, c)} ${piece ? (piece.k ? "Dama" : "Taş") : "boş"}`);
        square.addEventListener("click", onSquareClick);

        if (displayC === 0) {
          const rank = document.createElement("span");
          rank.className = "coord rank";
          rank.textContent = String(8 - r);
          square.appendChild(rank);
        }
        if (displayR === 7) {
          const file = document.createElement("span");
          file.className = "coord file";
          file.textContent = FILES[c];
          square.appendChild(file);
        }
        if (piece) {
          const stone = document.createElement("span");
          stone.className = `stone ${piece.c === "w" ? "white" : "black"} ${piece.k ? "king" : ""}`;
          square.appendChild(stone);
        }
        els.board.appendChild(square);
      }
    }
  }

  function renderStatus() {
    els.statusCard.classList.toggle("thinking", game.thinking);
    if (game.thinking) {
      els.statusTitle.textContent = "Bilgisayar düşünüyor";
      els.statusText.textContent = "Siyah en iyi alma yolunu arıyor.";
      return;
    }
    if (game.status === "finished") {
      els.statusTitle.textContent = `${colorName(game.winner)} kazandı`;
      els.statusText.textContent = game.mode === "ai" && game.winner === "w"
        ? "Tek oyuncu galibiyeti kaydediliyor."
        : "Dama maçı tamamlandı.";
      return;
    }
    const captures = allCaptureMoves(game.board, game.turn);
    els.statusTitle.textContent = captures.length ? `${colorName(game.turn)} almak zorunda` : `${colorName(game.turn)} oynar`;
    els.statusText.textContent = captures.length
      ? `En çok taş alan hamleler gösteriliyor: ${captures[0].captures.length} taş.`
      : (game.mode === "ai" ? "Tek oyuncu modu aktif." : "Bire bir mod aktif.");
  }

  function renderControls() {
    els.modeAi.classList.toggle("active", game.mode === "ai");
    els.modeLocal.classList.toggle("active", game.mode === "local");
    if (els.difficulty.value !== game.difficulty) els.difficulty.value = game.difficulty;
    els.difficulty.disabled = game.mode !== "ai";
    els.whitePlayer.textContent = game.mode === "ai" ? PLAYER_NAME : "Beyaz";
    els.blackPlayer.textContent = game.mode === "ai" ? "Bilgisayar" : "Siyah";
    els.moveCount.textContent = String(game.history.length);
  }

  function renderTaken() {
    els.takenWhite.innerHTML = game.takenBy.w.map(() => '<span class="pip black"></span>').join("");
    els.takenBlack.innerHTML = game.takenBy.b.map(() => '<span class="pip white"></span>').join("");
  }

  function renderMoves() {
    els.moveHistory.innerHTML = "";
    if (!game.history.length) {
      const empty = document.createElement("div");
      empty.className = "move-line";
      empty.innerHTML = "<span>1</span><b>...</b><b>...</b>";
      els.moveHistory.appendChild(empty);
      return;
    }
    for (let i = 0; i < game.history.length; i += 2) {
      const line = document.createElement("div");
      line.className = "move-line";
      const white = game.history[i]?.text || "";
      const black = game.history[i + 1]?.text || "";
      line.innerHTML = `<span>${Math.floor(i / 2) + 1}</span><b>${escapeHtml(white)}</b><b>${escapeHtml(black)}</b>`;
      els.moveHistory.appendChild(line);
    }
    els.moveHistory.scrollTop = els.moveHistory.scrollHeight;
  }

  function onSquareClick(event) {
    if (game.status !== "playing" || game.busy || game.thinking) return;
    if (game.mode === "ai" && game.turn === game.aiColor) return;

    const r = Number(event.currentTarget.dataset.r);
    const c = Number(event.currentTarget.dataset.c);
    const piece = game.board[r][c];

    if (game.selected) {
      const move = game.legal.find((item) => item.to.r === r && item.to.c === c);
      if (move) {
        commitMove(move);
        return;
      }
    }

    if (piece && piece.c === game.turn) {
      selectSquare(r, c);
      return;
    }

    game.selected = null;
    game.legal = [];
    renderBoard();
  }

  function selectSquare(r, c) {
    game.selected = { r, c };
    game.legal = legalMovesFor(game.board, game.turn)
      .filter((move) => move.from.r === r && move.from.c === c);
    renderBoard();
  }

  async function commitMove(move) {
    if (game.status !== "playing") return;
    const movingColor = game.turn;
    game.busy = true;
    await animateTravel(move);

    game.board = applyMove(game.board, move);
    if (move.captures.length) game.takenBy[movingColor].push(...move.captures.map((item) => ({ ...item.piece })));
    game.lastMove = copyMoveEdge(move);
    game.selected = null;
    game.legal = [];
    game.history.push({ color: movingColor, text: moveNotation(move) });
    game.turn = other(movingColor);
    game.busy = false;

    const winner = winnerAfter(game.board, game.turn);
    if (winner) {
      game.status = "finished";
      game.winner = winner;
    }

    renderAll();
    finishIfNeeded();

    if (game.mode === "ai" && game.status === "playing" && game.turn === game.aiColor) {
      queueAiMove();
    }
  }

  function queueAiMove() {
    game.thinking = true;
    renderStatus();
    window.setTimeout(() => {
      if (!game || game.status !== "playing" || game.turn !== game.aiColor) {
        if (game) {
          game.thinking = false;
          renderStatus();
        }
        return;
      }
      const move = chooseAiMove();
      game.thinking = false;
      if (move) commitMove(move);
    }, 520);
  }

  function chooseAiMove() {
    const moves = legalMovesFor(game.board, game.aiColor);
    if (!moves.length) return null;
    const difficulty = els.difficulty.value;

    if (difficulty === "casual") {
      return weightedMove(moves.map((move) => ({
        move,
        score: scoreMove(game.board, move, game.aiColor) + Math.random() * 90,
      })));
    }

    let best = null;
    let bestScore = -Infinity;
    for (const move of moves) {
      const board = applyMove(game.board, move);
      const score = difficulty === "master"
        ? minimax(board, other(game.aiColor), 2, -Infinity, Infinity, game.aiColor)
        : scoreMove(game.board, move, game.aiColor);
      const noisyScore = score + Math.random() * (difficulty === "master" ? 8 : 28);
      if (noisyScore > bestScore) {
        bestScore = noisyScore;
        best = move;
      }
    }
    return best || moves[Math.floor(Math.random() * moves.length)];
  }

  function weightedMove(scored) {
    const min = Math.min(...scored.map((item) => item.score));
    const weights = scored.map((item) => Math.max(8, item.score - min + 12));
    const total = weights.reduce((sum, value) => sum + value, 0);
    let pick = Math.random() * total;
    for (let i = 0; i < scored.length; i += 1) {
      pick -= weights[i];
      if (pick <= 0) return scored[i].move;
    }
    return scored[0].move;
  }

  function minimax(board, turn, depth, alpha, beta, aiColor) {
    const winner = winnerAfter(board, turn);
    if (winner) return winner === aiColor ? 100000 : -100000;
    if (depth === 0) return evaluateBoard(board, aiColor);
    const moves = legalMovesFor(board, turn);
    if (turn === aiColor) {
      let best = -Infinity;
      for (const move of moves) {
        const score = minimax(applyMove(board, move), other(turn), depth - 1, alpha, beta, aiColor);
        best = Math.max(best, score);
        alpha = Math.max(alpha, best);
        if (beta <= alpha) break;
      }
      return best;
    }
    let best = Infinity;
    for (const move of moves) {
      const score = minimax(applyMove(board, move), other(turn), depth - 1, alpha, beta, aiColor);
      best = Math.min(best, score);
      beta = Math.min(beta, best);
      if (beta <= alpha) break;
    }
    return best;
  }

  function scoreMove(board, move, color) {
    const next = applyMove(board, move);
    let score = evaluateBoard(next, color) - evaluateBoard(board, color);
    score += move.captures.reduce((sum, item) => sum + PIECE_VALUE[item.piece.k ? "king" : "man"] * 1.8, 0);
    if (move.promotes) score += 220;
    if (winnerAfter(next, other(color)) === color) score += 100000;
    score += centerBonus(move.to.r, move.to.c) * 10;
    return score;
  }

  function legalMovesFor(board, color) {
    const captures = allCaptureMoves(board, color);
    if (captures.length) return captures;
    const moves = [];
    forEachPiece(board, color, (piece, r, c) => {
      moves.push(...simpleMovesFor(board, r, c, piece));
    });
    return moves;
  }

  function allCaptureMoves(board, color) {
    const captures = [];
    forEachPiece(board, color, (piece, r, c) => {
      captures.push(...captureSequences(board, r, c, piece));
    });
    if (!captures.length) return captures;
    const max = Math.max(...captures.map((move) => move.captures.length));
    return captures.filter((move) => move.captures.length === max);
  }

  function simpleMovesFor(board, r, c, piece) {
    const moves = [];
    if (piece.k) {
      for (const [dr, dc] of DIRECTIONS.king) {
        let tr = r + dr;
        let tc = c + dc;
        while (inBounds(tr, tc) && !board[tr][tc]) {
          moves.push(baseMove(r, c, tr, tc, piece, []));
          tr += dr;
          tc += dc;
        }
      }
      return moves;
    }

    for (const [dr, dc] of DIRECTIONS[piece.c]) {
      const tr = r + dr;
      const tc = c + dc;
      if (inBounds(tr, tc) && !board[tr][tc]) {
        moves.push(baseMove(r, c, tr, tc, piece, []));
      }
    }
    return moves;
  }

  function captureSequences(board, r, c, piece) {
    const results = [];
    captureDfs(board, r, c, piece, { r, c }, [], [{ r, c }], null, results);
    return results;
  }

  function captureDfs(board, r, c, piece, origin, captures, path, prevDir, results) {
    const options = piece.k
      ? kingCaptureOptions(board, r, c, piece, prevDir)
      : manCaptureOptions(board, r, c, piece);

    if (!options.length) {
      if (captures.length) {
        const to = path[path.length - 1];
        const promoted = !piece.k && reachesKingRow(piece.c, to.r);
        results.push({
          from: { ...origin },
          to: { ...to },
          piece: { ...piece },
          captures: captures.map((item) => ({ ...item, piece: { ...item.piece } })),
          path: path.map((item) => ({ ...item })),
          promotes: promoted,
        });
      }
      return;
    }

    for (const option of options) {
      const next = cloneBoard(board);
      next[r][c] = null;
      next[option.capture.r][option.capture.c] = null;
      next[option.to.r][option.to.c] = { ...piece };
      captureDfs(
        next,
        option.to.r,
        option.to.c,
        piece,
        origin,
        [...captures, { r: option.capture.r, c: option.capture.c, piece: option.capture.piece }],
        [...path, { ...option.to }],
        option.dir,
        results,
      );
    }
  }

  function manCaptureOptions(board, r, c, piece) {
    const options = [];
    for (const [dr, dc] of DIRECTIONS[piece.c]) {
      const er = r + dr;
      const ec = c + dc;
      const lr = r + dr * 2;
      const lc = c + dc * 2;
      if (!inBounds(lr, lc)) continue;
      const enemy = board[er][ec];
      if (enemy && enemy.c !== piece.c && !board[lr][lc]) {
        options.push({
          to: { r: lr, c: lc },
          capture: { r: er, c: ec, piece: { ...enemy } },
          dir: [dr, dc],
        });
      }
    }
    return options;
  }

  function kingCaptureOptions(board, r, c, piece, prevDir) {
    const options = [];
    for (const [dr, dc] of DIRECTIONS.king) {
      if (prevDir && dr === -prevDir[0] && dc === -prevDir[1]) continue;
      let tr = r + dr;
      let tc = c + dc;
      while (inBounds(tr, tc) && !board[tr][tc]) {
        tr += dr;
        tc += dc;
      }
      if (!inBounds(tr, tc)) continue;
      const enemy = board[tr][tc];
      if (!enemy || enemy.c === piece.c) continue;
      let lr = tr + dr;
      let lc = tc + dc;
      while (inBounds(lr, lc) && !board[lr][lc]) {
        options.push({
          to: { r: lr, c: lc },
          capture: { r: tr, c: tc, piece: { ...enemy } },
          dir: [dr, dc],
        });
        lr += dr;
        lc += dc;
      }
    }
    return options;
  }

  function applyMove(board, move) {
    const next = cloneBoard(board);
    const piece = next[move.from.r][move.from.c];
    if (!piece) return next;
    next[move.from.r][move.from.c] = null;
    for (const capture of move.captures) {
      next[capture.r][capture.c] = null;
    }
    next[move.to.r][move.to.c] = {
      ...piece,
      k: piece.k || reachesKingRow(piece.c, move.to.r),
    };
    return next;
  }

  function winnerAfter(board, nextTurn) {
    const white = countPieces(board, "w");
    const black = countPieces(board, "b");
    if (!white) return "b";
    if (!black) return "w";
    if (!legalMovesFor(board, nextTurn).length) return other(nextTurn);
    return null;
  }

  function finishIfNeeded() {
    if (game.resultSaved || game.status !== "finished") return;
    const points = game.mode === "ai"
      ? (game.winner === "w" ? 24 : 0)
      : 14;
    if (points > 0) {
      saveScore(points, game.mode === "ai" ? "Dama galibiyeti kaydedildi." : "Bire bir dama sonucu kaydedildi.");
    }
  }

  async function saveScore(points, message) {
    if (game.resultSaved) return;
    game.resultSaved = true;
    if (!SCORE_ENABLED) {
      els.notice.textContent = message;
      return;
    }
    try {
      const response = await fetch(SCORE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ oyun: "Dama", puan: points }),
      });
      const data = await response.json();
      if (!data.ok) throw new Error(data.sebep || "Puan kaydedilemedi.");
      els.xpBadge.textContent = String(data.xp || 0);
      els.notice.textContent = `${message} +${data.xp || 0} XP`;
    } catch (error) {
      els.notice.textContent = error.message;
    }
  }

  function animateTravel(move) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return Promise.resolve();
    }
    const fromEl = els.board.querySelector(`[data-r="${move.from.r}"][data-c="${move.from.c}"] .stone`);
    const toCell = els.board.querySelector(`[data-r="${move.to.r}"][data-c="${move.to.c}"]`);
    if (!fromEl || !toCell) return Promise.resolve();

    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toCell.getBoundingClientRect();
    const clone = fromEl.cloneNode(true);
    clone.className = `flying-stone ${fromEl.classList.contains("white") ? "white" : "black"} ${fromEl.classList.contains("king") ? "king" : ""}`;
    clone.style.setProperty("--fly-size", `${fromRect.width}px`);
    clone.style.left = `${fromRect.left}px`;
    clone.style.top = `${fromRect.top}px`;
    clone.style.background = getComputedStyle(fromEl).background;
    clone.style.boxShadow = getComputedStyle(fromEl).boxShadow;
    document.body.appendChild(clone);
    fromEl.style.opacity = "0";

    const dx = toRect.left + toRect.width / 2 - (fromRect.left + fromRect.width / 2);
    const dy = toRect.top + toRect.height / 2 - (fromRect.top + fromRect.height / 2);

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        clone.style.transform = `translate(${dx}px, ${dy}px) scale(1.06)`;
      });
      window.setTimeout(() => {
        clone.remove();
        resolve();
      }, 290);
    });
  }

  function moveNotation(move) {
    const sep = move.captures.length ? "x" : "-";
    const path = [move.from, ...move.path.slice(1)];
    const text = path.map((item) => coordName(item.r, item.c)).join(sep);
    const crown = move.promotes ? "=D" : "";
    return `${text}${crown}`;
  }

  function baseMove(fromR, fromC, toR, toC, piece, captures) {
    return {
      from: { r: fromR, c: fromC },
      to: { r: toR, c: toC },
      piece: { ...piece },
      captures,
      path: [{ r: fromR, c: fromC }, { r: toR, c: toC }],
      promotes: !piece.k && reachesKingRow(piece.c, toR),
    };
  }

  function evaluateBoard(board, color) {
    let score = 0;
    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const piece = board[r][c];
        if (!piece) continue;
        const sign = piece.c === color ? 1 : -1;
        score += sign * (PIECE_VALUE[piece.k ? "king" : "man"] + positionalBonus(piece, r, c));
      }
    }
    return score;
  }

  function positionalBonus(piece, r, c) {
    let bonus = centerBonus(r, c) * 4;
    if (!piece.k) bonus += (piece.c === "w" ? 6 - r : r - 1) * 12;
    return bonus;
  }

  function centerBonus(r, c) {
    return 4 - (Math.abs(3.5 - r) + Math.abs(3.5 - c));
  }

  function forEachPiece(board, color, fn) {
    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const piece = board[r][c];
        if (piece && piece.c === color) fn(piece, r, c);
      }
    }
  }

  function countPieces(board, color) {
    let total = 0;
    forEachPiece(board, color, () => { total += 1; });
    return total;
  }

  function displayToBoard(displayR, displayC) {
    if (game.orientation === "w") return { r: displayR, c: displayC };
    return { r: 7 - displayR, c: 7 - displayC };
  }

  function reachesKingRow(color, r) {
    return color === "w" ? r === 0 : r === 7;
  }

  function copyMoveEdge(move) {
    return {
      from: { ...move.from },
      to: { ...move.to },
    };
  }

  function cloneBoard(board) {
    return board.map((row) => row.map((piece) => (piece ? { ...piece } : null)));
  }

  function inBounds(r, c) {
    return r >= 0 && r < 8 && c >= 0 && c < 8;
  }

  function other(color) {
    return color === "w" ? "b" : "w";
  }

  function colorName(color) {
    if (game.mode === "ai") return color === "w" ? "Sen" : "Bilgisayar";
    return color === "w" ? "Beyaz" : "Siyah";
  }

  function coordName(r, c) {
    return `${FILES[c]}${8 - r}`;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#39;",
    })[ch]);
  }
})();
