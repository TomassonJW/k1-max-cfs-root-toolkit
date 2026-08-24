export const GRID_SIZE = 11;
export const MIN_MM = 5;
export const MAX_MM = 295;
export const SPACING_MM = 29;

export function indexToMillimeters(index) {
  if (!Number.isInteger(index) || index < 0 || index >= GRID_SIZE) {
    throw new RangeError("index de grille invalide");
  }
  return MIN_MM + index * SPACING_MM;
}

export function displayRowOrder() {
  return Array.from({ length: GRID_SIZE }, (_, index) => GRID_SIZE - 1 - index);
}

export function allCellsForMode(mode, row, column, anchor = null) {
  if (![row, column].every((value) => Number.isInteger(value) && value >= 0 && value < GRID_SIZE)) {
    throw new RangeError("cellule invalide");
  }
  if (mode === "point") {
    return [[row, column]];
  }
  if (mode === "row") {
    return Array.from({ length: GRID_SIZE }, (_, currentColumn) => [row, currentColumn]);
  }
  if (mode === "column") {
    return Array.from({ length: GRID_SIZE }, (_, currentRow) => [currentRow, column]);
  }
  if (mode !== "region") {
    throw new RangeError("mode de sélection invalide");
  }
  if (anchor === null) {
    return [[row, column]];
  }
  const lowRow = Math.min(anchor[0], row);
  const highRow = Math.max(anchor[0], row);
  const lowColumn = Math.min(anchor[1], column);
  const highColumn = Math.max(anchor[1], column);
  if (highRow - lowRow + 1 > 3 || highColumn - lowColumn + 1 > 3) {
    throw new RangeError("une petite zone ne peut pas dépasser 3 × 3 points");
  }
  const cells = [];
  for (let currentRow = lowRow; currentRow <= highRow; currentRow += 1) {
    for (let currentColumn = lowColumn; currentColumn <= highColumn; currentColumn += 1) {
      cells.push([currentRow, currentColumn]);
    }
  }
  return cells;
}

export function selectionPayload(mode, cells) {
  if (!Array.isArray(cells) || cells.length === 0) {
    throw new RangeError("sélection vide");
  }
  const rows = cells.map(([row]) => row);
  const columns = cells.map(([, column]) => column);
  if (mode === "point") {
    return { mode, row: rows[0], column: columns[0] };
  }
  if (mode === "row") {
    return { mode, row: rows[0] };
  }
  if (mode === "column") {
    return { mode, column: columns[0] };
  }
  if (mode === "region") {
    return {
      mode,
      row_start: Math.min(...rows),
      row_end: Math.max(...rows),
      column_start: Math.min(...columns),
      column_end: Math.max(...columns),
    };
  }
  throw new RangeError("mode de sélection invalide");
}

export function projectSurface(matrix, width, height) {
  if (!Array.isArray(matrix) || matrix.length !== GRID_SIZE || matrix.some((row) => !Array.isArray(row) || row.length !== GRID_SIZE)) {
    throw new RangeError("matrice 11 × 11 attendue");
  }
  const values = matrix.flat().map(Number);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const amplitude = Math.max(maximum - minimum, 0.000001);
  const points = [];
  for (let row = 0; row < GRID_SIZE; row += 1) {
    for (let column = 0; column < GRID_SIZE; column += 1) {
      const xRatio = column / (GRID_SIZE - 1);
      const yRatio = row / (GRID_SIZE - 1);
      const zRatio = (Number(matrix[row][column]) - minimum) / amplitude;
      points.push({
        row,
        column,
        x: width * 0.5 + (xRatio - yRatio) * width * 0.32,
        y: height * 0.72 - (xRatio + yRatio) * height * 0.18 - zRatio * height * 0.31,
        value: Number(matrix[row][column]),
        zRatio,
      });
    }
  }
  return points;
}

export function nearestProjectedPoint(points, x, y, maximumDistance = 24) {
  let best = null;
  let bestSquared = maximumDistance * maximumDistance;
  for (const point of points) {
    const squared = (point.x - x) ** 2 + (point.y - y) ** 2;
    if (squared <= bestSquared) {
      best = point;
      bestSquared = squared;
    }
  }
  return best;
}
