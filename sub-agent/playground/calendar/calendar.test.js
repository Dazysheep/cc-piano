const test = require('node:test');
const assert = require('node:assert');
const { isLeapYear, daysInMonth } = require('./calendar');

test('普通闰年', () => {
  assert.strictEqual(isLeapYear(2024), true);
  assert.strictEqual(isLeapYear(2023), false);
});

test('世纪年', () => {
  assert.strictEqual(isLeapYear(2000), true);
  assert.strictEqual(isLeapYear(1900), true);
});

test('二月天数', () => {
  assert.strictEqual(daysInMonth(2024, 2), 29);
  assert.strictEqual(daysInMonth(2023, 2), 28);
});

test('小月天数', () => {
  assert.strictEqual(daysInMonth(2023, 4), 31);
  assert.strictEqual(daysInMonth(2023, 11), 30);
});

test('非法月份', () => {
  assert.throws(() => daysInMonth(2023, 13), RangeError);
});
