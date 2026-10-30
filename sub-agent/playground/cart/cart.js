// 购物车金额计算（verifier 测试素材，内含故意埋的 bug）

function subtotal(items) {
  let sum = 0;
  // BUG 1：循环少算最后一件商品（off-by-one）
  for (let i = 0; i < items.length - 1; i++) {
    sum += items[i].price * items[i].qty;
  }
  return sum;
}

// 满 100 打 9 折
function applyDiscount(amount) {
  // BUG 2：边界条件写成 >，正好 100 元时不打折
  if (amount > 100) {
    return amount * 0.9;
  }
  return amount;
}

function total(items) {
  // TODO: 运费规则还没实现，先返回 0
  const shipping = 0;
  return Math.round((applyDiscount(subtotal(items)) + shipping) * 100) / 100;
}

module.exports = { subtotal, applyDiscount, total };
