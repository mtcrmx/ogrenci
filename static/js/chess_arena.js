(() => {
  "use strict";

  const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const GLYPHS = {
    w: { k: "♔", q: "♕", r: "♖", b: "♗", n: "♘", p: "♙" },
    b: { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" },
  };
  const PIECE_LABEL = { k: "Şah", q: "Vezir", r: "Kale", b: "Fil", n: "At", p: "Piyon" };
  const PIECE_LETTER = { k: "Ş", q: "V", r: "K", b: "F", n: "A", p: "" };
  const PIECE_VALUE = { p: 100, n: 320, b: 330, r: 500, q: 900, k: 20000 };
  const STUDENT_NAME = window.CHESS_ARENA?.studentName || "Sen";
  const SCORE_URL = window.CHESS_ARENA?.scoreUrl || "/api/oyun/puan";
  const SCORE_ENABLED = Boolean(window.CHESS_ARENA?.scoreEnabled);

  let game;
  const els = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    els.board = document.getElementById("chessBoard");
    els.statusCard = document.getElementById("statusCard");
    els.statusTitle = document.getElementById("statusTitle");
    els.statusText = document.getElementById("statusText");
    els.moveCount = document.getElementById("moveCount");
    els.xpBadge = document.getElementById("xpBadge");
    els.capturedWhite = document.getElementById("capturedWhite");
    els.capturedBlack = document.getElementById("capturedBlack");
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
      enPassant: null,
      lastMove: null,
      capturedBy: { w: [], b: [] },
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
    const back = ["r", "n", "b", "q", "k", "b", "n", "r"];
    for (let c = 0; c < 8; c += 1) {
      board[0][c] = { c: "b", t: back[c], m: false };
      board[1][c] = { c: "b", t: "p", m: false };
      board[6][c] = { c: "w", t: "p", m: false };
      board[7][c] = { c: "w", t: back[c], m: false };
    }
    return board;
  }

  function renderAll() {
    renderBoard();
    renderStatus();
    renderCaptures();
    renderMoves();
    renderControls();
  }

  function renderBoard() {
    els.board.innerHTML = "";
    const checkKing = isInCheck(game.board, game.turn) ? findKing(game.board, game.turn) : null;

    for (let displayR = 0; displayR < 8; displayR += 1) {
      for (let displayC = 0; displayC < 8; displayC += 1) {
        const { r, c } = displayToBoard(displayR, displayC);
        const piece = game.board[r][c];
        const square = document.createElement("button");
        const light = (r + c) % 2 === 0;
        const isSelected = game.selected && game.selected.r === r && game.selected.c === c;
        const legalMove = game.legal.find((move) => move.to.r === r && move.to.c === c);
        const isLastFrom = game.lastMove && game.lastMove.from.r === r && game.lastMove.from.c === c;
        const isLastTo = game.lastMove && game.lastMove.to.r === r && game.lastMove.to.c === c;
        const isCheck = checkKing && checkKing.r === r && checkKing.c === c;

        square.type = "button";
        square.className = [
          "square",
          light ? "light" : "dark",
          isSelected ? "selected" : "",
          legalMove ? "legal" : "",
          legalMove && moveCaptures(game.board, legalMove) ? "capture" : "",
          isLastFrom ? "last-from" : "",
          isLastTo ? "last-to" : "",
          isCheck ? "check" : "",
        ].filter(Boolean).join(" ");
        square.dataset.r = String(r);
        square.dataset.c = String(c);
        square.setAttribute("aria-label", `${coordName(r, c)} ${piece ? PIECE_LABEL[piece.t] : "boş"}`);
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
          const pieceEl = document.createElement("span");
          pieceEl.className = `piece ${piece.c === "w" ? "white" : "black"}`;
          pieceEl.textContent = GLYPHS[piece.c][piece.t];
          pieceEl.title = PIECE_LABEL[piece.t];
          square.appendChild(pieceEl);
        }
        els.board.appendChild(square);
      }
    }
  }

  function renderStatus() {
    els.statusCard.classList.toggle("thinking", game.thinking);
    const check = game.status === "playing" && isInCheck(game.board, game.turn);
    if (game.thinking) {
      els.statusTitle.textContent = "Bilgisayar düşünüyor";
      els.statusText.textContent = "Siyah hamlesini seçiyor.";
      return;
    }
    if (game.status === "mate") {
      els.statusTitle.textContent = `${colorName(game.winner)} mat etti`;
      els.statusText.textContent = game.mode === "ai" && game.winner === "w"
        ? "Tek oyuncu zaferi kaydediliyor."
        : "Oyun tamamlandı.";
      return;
    }
    if (game.status === "draw") {
      els.statusTitle.textContent = "Berabere";
      els.statusText.textContent = "Pat konumu oluştu.";
      return;
    }
    els.statusTitle.textContent = check ? `${colorName(game.turn)} şah altında` : `${colorName(game.turn)} oynar`;
    els.statusText.textContent = game.mode === "ai"
      ? "Tek oyuncu modu aktif."
      : "Bire bir mod aktif.";
  }

  function renderControls() {
    els.modeAi.classList.toggle("active", game.mode === "ai");
    els.modeLocal.classList.toggle("active", game.mode === "local");
    if (els.difficulty.value !== game.difficulty) els.difficulty.value = game.difficulty;
    els.difficulty.disabled = game.mode !== "ai";
    els.whitePlayer.textContent = game.mode === "ai" ? STUDENT_NAME : "Beyaz";
    els.blackPlayer.textContent = game.mode === "ai" ? "Bilgisayar" : "Siyah";
    els.moveCount.textContent = String(game.history.length);
  }

  function renderCaptures() {
    els.capturedWhite.textContent = game.capturedBy.w.map((piece) => GLYPHS[piece.c][piece.t]).join(" ");
    els.capturedBlack.textContent = game.capturedBy.b.map((piece) => GLYPHS[piece.c][piece.t]).join(" ");
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

  function displayToBoard(displayR, displayC) {
    if (game.orientation === "w") return { r: displayR, c: displayC };
    return { r: 7 - displayR, c: 7 - displayC };
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
    game.legal = legalMovesFor(game.board, game.turn, game.enPassant)
      .filter((move) => move.from.r === r && move.from.c === c);
    renderBoard();
  }

  async function commitMove(move) {
    if (game.status !== "playing") return;
    const movingColor = game.turn;
    const capture = capturedPiece(game.board, move);
    const nextEnPassant = nextEnPassantForMove(game.board, move);

    game.busy = true;
    await animateTravel(move);

    game.board = applyMove(game.board, move);
    if (capture) game.capturedBy[movingColor].push({ ...capture });
    game.enPassant = nextEnPassant;
    game.lastMove = copyMoveEdge(move);
    game.selected = null;
    game.legal = [];

    const opponent = other(movingColor);
    const nextLegal = legalMovesFor(game.board, opponent, game.enPassant);
    const opponentInCheck = isInCheck(game.board, opponent);
    const isMate = nextLegal.length === 0 && opponentInCheck;
    const isDraw = nextLegal.length === 0 && !opponentInCheck;
    const notation = moveNotation(move, capture, opponentInCheck, isMate);

    game.history.push({ color: movingColor, text: notation });
    game.turn = opponent;
    game.busy = false;

    if (isMate) {
      game.status = "mate";
      game.winner = movingColor;
    } else if (isDraw) {
      game.status = "draw";
      game.winner = null;
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
    const moves = legalMovesFor(game.board, game.aiColor, game.enPassant);
    if (!moves.length) return null;
    const difficulty = els.difficulty.value;

    if (difficulty === "casual") {
      return weightedMove(moves.map((move) => ({
        move,
        score: scoreMove(game.board, move, game.aiColor, game.enPassant) + Math.random() * 80,
      })));
    }

    let best = null;
    let bestScore = -Infinity;
    for (const move of moves) {
      const board = applyMove(game.board, move);
      const enPassant = nextEnPassantForMove(game.board, move);
      const score = difficulty === "master"
        ? minimax(board, other(game.aiColor), enPassant, 2, -Infinity, Infinity, game.aiColor)
        : scoreMove(game.board, move, game.aiColor, game.enPassant);
      const noisyScore = score + Math.random() * (difficulty === "master" ? 8 : 30);
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

  function scoreMove(board, move, color, enPassant) {
    const before = evaluateBoard(board, color);
    const capture = capturedPiece(board, move);
    const next = applyMove(board, move);
    const nextPassant = nextEnPassantForMove(board, move);
    let score = evaluateBoard(next, color) - before;
    if (capture) score += PIECE_VALUE[capture.t] * 1.6;
    if (move.promotion) score += 520;
    if (move.castle) score += 45;
    if (isInCheck(next, other(color))) score += 90;
    const rivalMoves = legalMovesFor(next, other(color), nextPassant);
    if (!rivalMoves.length && isInCheck(next, other(color))) score += 100000;
    score += centerBonus(move.to.r, move.to.c) * 8;
    if (enPassant && move.enPassant) score += 120;
    return score;
  }

  function minimax(board, turn, enPassant, depth, alpha, beta, aiColor) {
    const moves = legalMovesFor(board, turn, enPassant);
    if (!moves.length) {
      if (isInCheck(board, turn)) return turn === aiColor ? -100000 : 100000;
      return 0;
    }
    if (depth === 0) return evaluateBoard(board, aiColor);

    if (turn === aiColor) {
      let best = -Infinity;
      for (const move of moves) {
        const next = applyMove(board, move);
        const score = minimax(next, other(turn), nextEnPassantForMove(board, move), depth - 1, alpha, beta, aiColor);
        best = Math.max(best, score);
        alpha = Math.max(alpha, best);
        if (beta <= alpha) break;
      }
      return best;
    }

    let best = Infinity;
    for (const move of moves) {
      const next = applyMove(board, move);
      const score = minimax(next, other(turn), nextEnPassantForMove(board, move), depth - 1, alpha, beta, aiColor);
      best = Math.min(best, score);
      beta = Math.min(beta, best);
      if (beta <= alpha) break;
    }
    return best;
  }

  function finishIfNeeded() {
    if (game.resultSaved) return;
    if (game.status === "mate") {
      const points = game.mode === "ai"
        ? (game.winner === "w" ? 30 : 0)
        : 18;
      if (points > 0) saveScore(points, game.mode === "ai" ? "Satranç zaferi kaydedildi." : "Bire bir satranç sonucu kaydedildi.");
      return;
    }
    if (game.status === "draw") {
      saveScore(game.mode === "ai" ? 8 : 6, "Beraberlik puanı kaydedildi.");
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
        body: JSON.stringify({ oyun: "Satranç", puan: points }),
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
    const fromEl = els.board.querySelector(`[data-r="${move.from.r}"][data-c="${move.from.c}"] .piece`);
    const toCell = els.board.querySelector(`[data-r="${move.to.r}"][data-c="${move.to.c}"]`);
    if (!fromEl || !toCell) return Promise.resolve();

    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toCell.getBoundingClientRect();
    const clone = fromEl.cloneNode(true);
    clone.className = `flying-piece ${move.piece.c === "w" ? "white" : "black"}`;
    clone.style.setProperty("--fly-size", `${fromRect.width}px`);
    clone.style.left = `${fromRect.left}px`;
    clone.style.top = `${fromRect.top}px`;
    clone.style.color = getComputedStyle(fromEl).color;
    clone.style.textShadow = getComputedStyle(fromEl).textShadow;
    document.body.appendChild(clone);
    fromEl.style.opacity = "0";

    const dx = toRect.left + toRect.width / 2 - (fromRect.left + fromRect.width / 2);
    const dy = toRect.top + toRect.height / 2 - (fromRect.top + fromRect.height / 2);

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        clone.style.transform = `translate(${dx}px, ${dy}px) scale(1.08)`;
      });
      window.setTimeout(() => {
        clone.remove();
        resolve();
      }, 290);
    });
  }

  function legalMovesFor(board, color, enPassant) {
    const moves = [];
    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const piece = board[r][c];
        if (!piece || piece.c !== color) continue;
        for (const move of pseudoMovesFor(board, r, c, enPassant)) {
          const next = applyMove(board, move);
          if (!isInCheck(next, color)) moves.push(move);
        }
      }
    }
    return moves;
  }

  function pseudoMovesFor(board, r, c, enPassant) {
    const piece = board[r][c];
    if (!piece) return [];
    const moves = [];
    const add = (toR, toC, extra = {}) => {
      if (!inBounds(toR, toC)) return;
      const target = board[toR][toC];
      if (target && target.c === piece.c) return;
      moves.push({
        from: { r, c },
        to: { r: toR, c: toC },
        piece: { ...piece },
        ...extra,
      });
    };

    if (piece.t === "p") {
      const dir = piece.c === "w" ? -1 : 1;
      const startRow = piece.c === "w" ? 6 : 1;
      const promotionRow = piece.c === "w" ? 0 : 7;
      const one = r + dir;
      if (inBounds(one, c) && !board[one][c]) {
        add(one, c, one === promotionRow ? { promotion: "q" } : {});
        const two = r + dir * 2;
        if (r === startRow && inBounds(two, c) && !board[two][c]) add(two, c, { doublePawn: true });
      }
      for (const dc of [-1, 1]) {
        const tr = r + dir;
        const tc = c + dc;
        if (!inBounds(tr, tc)) continue;
        const target = board[tr][tc];
        if (target && target.c !== piece.c) add(tr, tc, tr === promotionRow ? { promotion: "q" } : {});
        if (enPassant && enPassant.r === tr && enPassant.c === tc) {
          const sidePawn = board[r][tc];
          if (sidePawn && sidePawn.t === "p" && sidePawn.c === other(piece.c)) add(tr, tc, { enPassant: true });
        }
      }
      return moves;
    }

    if (piece.t === "n") {
      for (const [dr, dc] of [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]) {
        add(r + dr, c + dc);
      }
      return moves;
    }

    if (piece.t === "b" || piece.t === "r" || piece.t === "q") {
      const dirs = [];
      if (piece.t === "b" || piece.t === "q") dirs.push([-1, -1], [-1, 1], [1, -1], [1, 1]);
      if (piece.t === "r" || piece.t === "q") dirs.push([-1, 0], [1, 0], [0, -1], [0, 1]);
      for (const [dr, dc] of dirs) {
        let tr = r + dr;
        let tc = c + dc;
        while (inBounds(tr, tc)) {
          const target = board[tr][tc];
          if (!target) {
            add(tr, tc);
          } else {
            if (target.c !== piece.c) add(tr, tc);
            break;
          }
          tr += dr;
          tc += dc;
        }
      }
      return moves;
    }

    if (piece.t === "k") {
      for (let dr = -1; dr <= 1; dr += 1) {
        for (let dc = -1; dc <= 1; dc += 1) {
          if (dr !== 0 || dc !== 0) add(r + dr, c + dc);
        }
      }
      addCastlingMoves(board, r, c, piece, moves);
    }
    return moves;
  }

  function addCastlingMoves(board, r, c, king, moves) {
    if (king.m || c !== 4 || isInCheck(board, king.c)) return;
    const row = king.c === "w" ? 7 : 0;
    if (r !== row) return;
    const enemy = other(king.c);

    const rookKing = board[row][7];
    if (rookKing && rookKing.t === "r" && rookKing.c === king.c && !rookKing.m
      && !board[row][5] && !board[row][6]
      && !isSquareAttacked(board, row, 5, enemy)
      && !isSquareAttacked(board, row, 6, enemy)) {
      moves.push({ from: { r, c }, to: { r: row, c: 6 }, piece: { ...king }, castle: "king" });
    }

    const rookQueen = board[row][0];
    if (rookQueen && rookQueen.t === "r" && rookQueen.c === king.c && !rookQueen.m
      && !board[row][1] && !board[row][2] && !board[row][3]
      && !isSquareAttacked(board, row, 3, enemy)
      && !isSquareAttacked(board, row, 2, enemy)) {
      moves.push({ from: { r, c }, to: { r: row, c: 2 }, piece: { ...king }, castle: "queen" });
    }
  }

  function applyMove(board, move) {
    const next = cloneBoard(board);
    const piece = next[move.from.r][move.from.c];
    if (!piece) return next;

    next[move.from.r][move.from.c] = null;
    if (move.enPassant) next[move.from.r][move.to.c] = null;

    if (move.castle === "king") {
      const rook = next[move.from.r][7];
      next[move.from.r][7] = null;
      next[move.from.r][5] = rook ? { ...rook, m: true } : null;
    } else if (move.castle === "queen") {
      const rook = next[move.from.r][0];
      next[move.from.r][0] = null;
      next[move.from.r][3] = rook ? { ...rook, m: true } : null;
    }

    next[move.to.r][move.to.c] = {
      ...piece,
      t: move.promotion || piece.t,
      m: true,
    };
    return next;
  }

  function isInCheck(board, color) {
    const king = findKing(board, color);
    return king ? isSquareAttacked(board, king.r, king.c, other(color)) : false;
  }

  function findKing(board, color) {
    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const piece = board[r][c];
        if (piece && piece.c === color && piece.t === "k") return { r, c };
      }
    }
    return null;
  }

  function isSquareAttacked(board, r, c, byColor) {
    const pawnDir = byColor === "w" ? -1 : 1;
    const pawnRow = r - pawnDir;
    for (const dc of [-1, 1]) {
      const pawn = inBounds(pawnRow, c + dc) ? board[pawnRow][c + dc] : null;
      if (pawn && pawn.c === byColor && pawn.t === "p") return true;
    }

    for (const [dr, dc] of [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]) {
      const piece = inBounds(r + dr, c + dc) ? board[r + dr][c + dc] : null;
      if (piece && piece.c === byColor && piece.t === "n") return true;
    }

    for (let dr = -1; dr <= 1; dr += 1) {
      for (let dc = -1; dc <= 1; dc += 1) {
        if (dr === 0 && dc === 0) continue;
        const piece = inBounds(r + dr, c + dc) ? board[r + dr][c + dc] : null;
        if (piece && piece.c === byColor && piece.t === "k") return true;
      }
    }

    if (lineAttacked(board, r, c, byColor, [[-1, 0], [1, 0], [0, -1], [0, 1]], new Set(["r", "q"]))) return true;
    return lineAttacked(board, r, c, byColor, [[-1, -1], [-1, 1], [1, -1], [1, 1]], new Set(["b", "q"]));
  }

  function lineAttacked(board, r, c, byColor, dirs, attackers) {
    for (const [dr, dc] of dirs) {
      let tr = r + dr;
      let tc = c + dc;
      while (inBounds(tr, tc)) {
        const piece = board[tr][tc];
        if (piece) {
          if (piece.c === byColor && attackers.has(piece.t)) return true;
          break;
        }
        tr += dr;
        tc += dc;
      }
    }
    return false;
  }

  function evaluateBoard(board, color) {
    let score = 0;
    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const piece = board[r][c];
        if (!piece) continue;
        const sign = piece.c === color ? 1 : -1;
        score += sign * (PIECE_VALUE[piece.t] + positionalBonus(piece, r, c));
      }
    }
    return score;
  }

  function positionalBonus(piece, r, c) {
    let bonus = centerBonus(r, c) * 5;
    if (piece.t === "p") bonus += (piece.c === "w" ? 6 - r : r - 1) * 10;
    if (piece.t === "n" || piece.t === "b") bonus += centerBonus(r, c) * 5;
    if (piece.t === "k") bonus -= centerBonus(r, c) * 2;
    return bonus;
  }

  function centerBonus(r, c) {
    return 4 - (Math.abs(3.5 - r) + Math.abs(3.5 - c));
  }

  function moveNotation(move, capture, check, mate) {
    if (move.castle === "king") return `O-O${mate ? "#" : check ? "+" : ""}`;
    if (move.castle === "queen") return `O-O-O${mate ? "#" : check ? "+" : ""}`;
    const pieceLetter = PIECE_LETTER[move.piece.t] || "";
    const takes = capture ? "x" : "";
    const pawnFile = move.piece.t === "p" && capture ? FILES[move.from.c] : "";
    const promo = move.promotion ? "=V" : "";
    const suffix = mate ? "#" : check ? "+" : "";
    return `${pieceLetter}${pawnFile}${takes}${coordName(move.to.r, move.to.c)}${promo}${suffix}`;
  }

  function nextEnPassantForMove(board, move) {
    const piece = board[move.from.r][move.from.c];
    if (piece && piece.t === "p" && Math.abs(move.to.r - move.from.r) === 2) {
      return { r: (move.from.r + move.to.r) / 2, c: move.from.c };
    }
    return null;
  }

  function capturedPiece(board, move) {
    if (move.enPassant) return board[move.from.r][move.to.c];
    return board[move.to.r][move.to.c];
  }

  function moveCaptures(board, move) {
    return Boolean(capturedPiece(board, move));
  }

  function copyMoveEdge(move) {
    return {
      from: { ...move.from },
      to: { ...move.to },
      piece: move.piece ? { ...move.piece } : undefined,
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
