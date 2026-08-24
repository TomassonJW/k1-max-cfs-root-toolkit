import assert from "node:assert/strict";
import test from "node:test";

import {
  allCellsForMode,
  displayRowOrder,
  indexToMillimeters,
  nearestProjectedPoint,
  projectSurface,
  selectionPayload,
} from "../packages/k1-control-v1/mesh-editor-offline-v1/www/ui-geometry.mjs";

test("l'orientation publique conserve Y croissant dans les données et l'arrière en haut", () => {
  assert.equal(indexToMillimeters(0), 5);
  assert.equal(indexToMillimeters(10), 295);
  assert.deepEqual(displayRowOrder(), [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]);
});

test("les quatre modes de sélection produisent les cellules attendues", () => {
  assert.deepEqual(allCellsForMode("point", 2, 3), [[2, 3]]);
  assert.equal(allCellsForMode("row", 2, 3).length, 11);
  assert.equal(allCellsForMode("column", 2, 3).length, 11);
  const region = allCellsForMode("region", 5, 6, [3, 4]);
  assert.equal(region.length, 9);
  assert.deepEqual(region[0], [3, 4]);
  assert.deepEqual(region.at(-1), [5, 6]);
});

test("une zone supérieure à 3 par 3 est refusée", () => {
  assert.throws(
    () => allCellsForMode("region", 3, 3, [0, 0]),
    /3 × 3/,
  );
});

test("le payload d'une zone reste exprimé par indices source", () => {
  const cells = allCellsForMode("region", 4, 6, [3, 5]);
  assert.deepEqual(selectionPayload("region", cells), {
    mode: "region",
    row_start: 3,
    row_end: 4,
    column_start: 5,
    column_end: 6,
  });
});

test("l'aperçu projette 121 points et permet une sélection sans déplacement vertical", () => {
  const matrix = Array.from({ length: 11 }, (_, row) =>
    Array.from({ length: 11 }, (_, column) => row * 0.01 + column * 0.001),
  );
  const points = projectSurface(matrix, 920, 620);
  assert.equal(points.length, 121);
  const target = points.find((point) => point.row === 7 && point.column === 2);
  assert.deepEqual(
    nearestProjectedPoint(points, target.x, target.y, 1),
    target,
  );
  assert.equal(nearestProjectedPoint(points, -100, -100, 1), null);
});
