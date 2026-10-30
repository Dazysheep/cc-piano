// 公历（格里高利历）日期工具

/**
 * 判断闰年：能被 4 整除且不能被 100 整除，或能被 400 整除。
 * @param {number} year
 * @returns {boolean}
 */
function isLeapYear(year) {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

/**
 * 某年某月的天数。
 * @param {number} year
 * @param {number} month 1-12
 * @returns {number}
 */
function daysInMonth(year, month) {
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`month must be 1-12, got ${month}`);
  }
  if (month === 2 && isLeapYear(year)) return 29;
  return DAYS[month - 1];
}

module.exports = { isLeapYear, daysInMonth };
