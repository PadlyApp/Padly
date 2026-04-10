'use client';

import { Box } from '@mantine/core';

/**
 * Renders a bar chart of price distribution bins above a RangeSlider.
 * Bins within the selected range are highlighted in teal; others are grey.
 *
 * @param {{ bins: array, maxCount: number, rangeValue: [number, number] }} props
 */
export function PriceHistogram({ bins, maxCount, rangeValue }) {
  if (!bins || bins.length === 0) return null;
  const [lo, hi] = rangeValue;
  return (
    <Box style={{ display: 'flex', alignItems: 'flex-end', height: 80, gap: 2, marginBottom: -1 }}>
      {bins.map((bin, i) => {
        const heightPct = maxCount > 0 ? Math.max((bin.count / maxCount) * 100, 2) : 2;
        const binMid = (bin.range_min + bin.range_max) / 2;
        const active = binMid >= lo && binMid <= hi;
        return (
          <Box
            key={i}
            style={{
              flex: 1,
              height: `${heightPct}%`,
              backgroundColor: active ? '#20c997' : '#d0d5da',
              borderRadius: '2px 2px 0 0',
              transition: 'background-color 0.08s ease, height 0.2s ease',
            }}
          />
        );
      })}
    </Box>
  );
}
