const test = require('node:test');
const assert = require('node:assert');
const { subtotal, applyDiscount, total } = require('./cart');

test('subtotal 累加所有商品', () => {
  assert.strictEqual(subtotal([{ price: 10, qty: 2 }, { price: 5, qty: 1 }]), 25);
});

test('满 100 打 9 折（含 100）', () => {
  assert.strictEqual(applyDiscount(100), 90);
  assert.strictEqual(applyDiscount(99), 99);
});

test('total 综合计算', () => {
  assert.strictEqual(total([{ price: 60, qty: 1 }, { price: 50, qty: 1 }]), 99);
});
