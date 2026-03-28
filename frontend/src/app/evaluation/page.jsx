'use client';

import { useState, useEffect } from 'react';
import {
  Box, Container, Title, Text, Select, Button, Stack, Group,
  Card, SimpleGrid, Table, Loader, Alert, Badge, Divider, Tooltip,
} from '@mantine/core';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function EvaluationPage() {
  return (
    <ProtectedRoute>
      <EvaluationPageContent />
    </ProtectedRoute>
  );
}

// ── small helpers ─────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, plain }) {
  return (
    <Card shadow="sm" radius="lg" style={{ border: '1px solid #f1f1f1', padding: '1.5rem' }}>
      <Text size="sm" c="dimmed" mb={4}>{label}</Text>
      <Text fw={600} style={{ fontSize: '1.75rem', color: '#111', lineHeight: 1 }}>
        {value ?? '—'}
      </Text>
      {sub && <Text size="xs" c="dimmed" mt={4}>{sub}</Text>}
      {plain && (
        <Text size="xs" mt={8} style={{ color: '#555', borderTop: '1px solid #f1f1f1', paddingTop: 8, lineHeight: 1.4 }}>
          {plain}
        </Text>
      )}
    </Card>
  );
}

/** Map a 0-1 score to a teal-tinted background colour. */
function scoreToColor(score) {
  if (score == null) return '#f8f8f8';
  // 0 → white, 1 → teal (#20c997)
  const t = Math.max(0, Math.min(1, score));
  const r = Math.round(255 - t * (255 - 32));
  const g = Math.round(255 - t * (255 - 201));
  const b = Math.round(255 - t * (255 - 151));
  return `rgb(${r},${g},${b})`;
}

function textColor(score) {
  if (score == null) return '#999';
  return score > 0.6 ? '#fff' : '#111';
}

// ── main component ────────────────────────────────────────────────────────────

function EvaluationPageContent() {
  const [models, setModels]         = useState([]);
  const [selected, setSelected]     = useState(null);
  const [running, setRunning]       = useState(false);

  // independent result states for the two parallel fetches
  const [metricsStatus,  setMetricsStatus]  = useState('idle');   // idle|loading|done|error
  const [metricsResult,  setMetricsResult]  = useState(null);
  const [metricsError,   setMetricsError]   = useState('');

  const [matrixStatus,   setMatrixStatus]   = useState('idle');
  const [matrixResult,   setMatrixResult]   = useState(null);
  const [matrixError,    setMatrixError]    = useState('');

  useEffect(() => {
    fetch(`${API}/api/evaluation/models`)
      .then((r) => r.json())
      .then((list) => {
        setModels(list);
        if (list.length > 0) setSelected(list[0]);
      })
      .catch(() => setModels([]));
  }, []);

  const runEval = async () => {
    if (!selected || running) return;
    setRunning(true);

    setMetricsStatus('loading');
    setMetricsResult(null);
    setMetricsError('');
    setMatrixStatus('loading');
    setMatrixResult(null);
    setMatrixError('');

    const fetchMetrics = fetch(`${API}/api/evaluation/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: selected }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const d = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(d.detail || res.statusText);
        }
        return res.json();
      })
      .then((data) => { setMetricsResult(data); setMetricsStatus('done'); })
      .catch((err) => { setMetricsError(err.message); setMetricsStatus('error'); });

    const fetchMatrix = fetch(`${API}/api/evaluation/category-eval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: selected }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const d = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(d.detail || res.statusText);
        }
        return res.json();
      })
      .then((data) => { setMatrixResult(data); setMatrixStatus('done'); })
      .catch((err) => { setMatrixError(err.message); setMatrixStatus('error'); });

    await Promise.allSettled([fetchMetrics, fetchMatrix]);
    setRunning(false);
  };

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 3rem' }}>

        {/* ── Header ── */}
        <Stack align="center" gap="sm" mb={40}>
          <Title order={1} style={{ fontSize: '2.5rem', fontWeight: 500, color: '#111', textAlign: 'center' }}>
            Model Evaluation
          </Title>
          <Text size="lg" c="dimmed" style={{ maxWidth: '44rem', textAlign: 'center' }}>
            Two-tower BCE model — <strong>categories removed from inputs</strong>, used only for evaluation
          </Text>
        </Stack>

        {/* ── Methodology banner ── */}
        <Card
          shadow="sm"
          radius="lg"
          mb={40}
          style={{ border: '1px solid #e9f7f2', backgroundColor: '#f4fdf9', padding: '1.5rem 2rem' }}
        >
          <Group gap="md" wrap="wrap" align="flex-start">
            <Stack gap={6} style={{ flex: 1, minWidth: 220 }}>
              <Group gap="xs">
                <Badge color="red" variant="light" size="lg">✗ No categories in model input</Badge>
                <Badge color="teal" variant="light" size="lg">✓ Categories used for evaluation</Badge>
              </Group>
              <Text size="sm" style={{ color: '#333', lineHeight: 1.6 }}>
                The model was trained on raw renter preferences and listing attributes only — it never
                saw a category label. Post-hoc, we assign each user and each listing to one of 6
                categories using deterministic rules, then ask: <em>does the model score category-matched
                pairs higher than mismatched ones?</em> If the diagonal of the matrix below is darkest,
                the model implicitly learned the category structure from raw features alone.
              </Text>
            </Stack>
            <Box style={{ minWidth: 200 }}>
              <Text size="xs" fw={600} c="dimmed" mb={6} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                6 categories
              </Text>
              {[
                ['0', 'Budget Compact',     'price < $900, ≤1 bed'],
                ['1', 'Spacious Family',    '3+ beds, large sqft'],
                ['2', 'Pet-Friendly',       'cats & dogs allowed'],
                ['3', 'Premium / Luxury',   'price > $1 500 + amenities'],
                ['4', 'Urban Convenience',  'moderate apartments'],
                ['5', 'Accessible Modern',  'wheelchair / EV'],
              ].map(([id, name, rule]) => (
                <Group key={id} gap={6} mb={2}>
                  <Badge size="xs" variant="filled" color="gray" style={{ minWidth: 18, textAlign: 'center' }}>{id}</Badge>
                  <Text size="xs" fw={500} style={{ color: '#111' }}>{name}</Text>
                  <Text size="xs" c="dimmed">— {rule}</Text>
                </Group>
              ))}
            </Box>
          </Group>
        </Card>

        {/* ── Controls ── */}
        <Card shadow="sm" radius="lg" style={{ border: '1px solid #f1f1f1', padding: '2rem', maxWidth: 560, margin: '0 auto 48px' }}>
          <Stack gap="lg">
            <Select
              label="Model"
              placeholder="Select a model"
              data={models}
              value={selected}
              onChange={setSelected}
              disabled={models.length === 0 || running}
              styles={{ label: { fontWeight: 500, marginBottom: 6 } }}
            />
            <Button
              size="md"
              style={{ backgroundColor: '#20c997' }}
              onClick={runEval}
              disabled={!selected || running}
              onMouseEnter={(e) => { if (selected && !running) e.currentTarget.style.backgroundColor = '#12b886'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#20c997'; }}
            >
              {running ? 'Running...' : 'Run Evaluation'}
            </Button>
            {running && (
              <Group gap="sm">
                <Loader size="sm" color="teal" />
                <Text size="sm" c="dimmed">Running category matrix + metrics in parallel…</Text>
              </Group>
            )}
          </Stack>
        </Card>

        {/* ══════════════════════════════════════════════════════════════════
            SECTION 1 — Category Cross-Prediction Matrix
        ══════════════════════════════════════════════════════════════════ */}
        {(matrixStatus !== 'idle') && (
          <Stack gap="lg" mb={56}>
            <div>
              <Title order={2} style={{ color: '#111', fontWeight: 500, fontSize: '1.6rem' }} mb={4}>
                Category Cross-Prediction Matrix
              </Title>
              <Text size="sm" c="dimmed">
                Each cell = mean model score for pairs where the user belongs to row-category and the
                listing belongs to column-category. <strong>Darker diagonal cells = the model matched
                them without knowing the labels.</strong>
              </Text>
            </div>

            {matrixStatus === 'loading' && (
              <Group gap="sm">
                <Loader size="sm" color="teal" />
                <Text size="sm" c="dimmed">Running category eval…</Text>
              </Group>
            )}

            {matrixStatus === 'error' && (
              <Alert color="red" radius="lg">{matrixError}</Alert>
            )}

            {matrixStatus === 'done' && matrixResult && (() => {
              const { category_names, matrix, counts } = matrixResult;
              return (
                <Card shadow="sm" radius="lg" style={{ border: '1px solid #f1f1f1', overflowX: 'auto' }}>
                  <Text size="xs" c="dimmed" mb="md">
                    Rows = user category &nbsp;·&nbsp; Columns = listing category &nbsp;·&nbsp;
                    Hover a cell to see pair count
                  </Text>
                  <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 580 }}>
                    <thead>
                      <tr>
                        <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 500, whiteSpace: 'nowrap' }}>
                          User ↓ &nbsp; Listing →
                        </th>
                        {category_names.map((name, ci) => (
                          <th key={ci} style={{ padding: '8px 10px', textAlign: 'center', fontSize: 11, color: '#555', fontWeight: 600, whiteSpace: 'nowrap' }}>
                            {ci} · {name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {matrix.map((row, ri) => (
                        <tr key={ri}>
                          <td style={{ padding: '8px 12px', fontSize: 12, fontWeight: 600, color: '#555', whiteSpace: 'nowrap', borderRight: '1px solid #f1f1f1' }}>
                            {ri} · {category_names[ri]}
                          </td>
                          {row.map((score, ci) => {
                            const isDiag = ri === ci;
                            const bg = scoreToColor(score);
                            const fg = textColor(score);
                            const n = counts[ri][ci];
                            return (
                              <Tooltip
                                key={ci}
                                label={`${counts[ri][ci].toLocaleString()} pairs`}
                                position="top"
                                withArrow
                              >
                                <td
                                  style={{
                                    padding: '10px 8px',
                                    textAlign: 'center',
                                    backgroundColor: bg,
                                    color: fg,
                                    fontSize: 13,
                                    fontWeight: isDiag ? 700 : 400,
                                    border: isDiag ? '2px solid #20c997' : '1px solid #f0f0f0',
                                    cursor: 'default',
                                    minWidth: 72,
                                  }}
                                >
                                  {score != null ? score.toFixed(3) : '—'}
                                  {isDiag && (
                                    <div style={{ fontSize: 9, marginTop: 2, opacity: 0.85 }}>
                                      ◆ diagonal
                                    </div>
                                  )}
                                  <div style={{ fontSize: 9, opacity: 0.6, marginTop: 1 }}>
                                    n={n.toLocaleString()}
                                  </div>
                                </td>
                              </Tooltip>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* colour legend */}
                  <Group mt="md" gap="xs" align="center">
                    <Text size="xs" c="dimmed">Score:</Text>
                    {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((v) => (
                      <Box
                        key={v}
                        style={{
                          width: 28,
                          height: 14,
                          borderRadius: 3,
                          backgroundColor: scoreToColor(v),
                          border: '1px solid #e0e0e0',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Text size={9} style={{ color: textColor(v) }}>{v.toFixed(1)}</Text>
                      </Box>
                    ))}
                    <Text size="xs" c="dimmed">→ darker = higher model score</Text>
                  </Group>
                </Card>
              );
            })()}
          </Stack>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            SECTION 2 — Technical Metrics
        ══════════════════════════════════════════════════════════════════ */}
        {(metricsStatus !== 'idle') && (
          <Stack gap={48}>
            <Divider label={<Text size="sm" c="dimmed" fw={500}>Technical Metrics</Text>} labelPosition="left" />

            {metricsStatus === 'loading' && (
              <Group gap="sm">
                <Loader size="sm" color="teal" />
                <Text size="sm" c="dimmed">Running inference on test pairs…</Text>
              </Group>
            )}

            {metricsStatus === 'error' && (
              <Alert color="red" radius="lg" style={{ maxWidth: 640 }}>{metricsError}</Alert>
            )}

            {metricsStatus === 'done' && metricsResult && (
              <Stack gap={48}>
                {/* summary badges */}
                <Group gap="md" wrap="wrap">
                  <Badge size="lg" variant="light" color="teal">Model: {metricsResult.model}</Badge>
                  <Badge size="lg" variant="light" color="gray">{metricsResult.test_pairs.toLocaleString()} test pairs</Badge>
                  <Badge size="lg" variant="light" color="green">{metricsResult.positives.toLocaleString()} positives</Badge>
                  <Badge size="lg" variant="light" color="red">{metricsResult.negatives.toLocaleString()} negatives</Badge>
                </Group>

                {/* Regression metrics */}
                {metricsResult.regression ? (
                  <Stack gap="lg">
                    <div>
                      <Title order={3} style={{ color: '#111', fontWeight: 500 }} mb={4}>
                        Model vs Deterministic Score
                      </Title>
                      <Text size="sm" c="dimmed">How closely the neural net tracks the weighted formula output</Text>
                    </div>
                    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="lg">
                      <StatCard
                        label="Average Error"
                        value={metricsResult.regression.mae.toFixed(4)}
                        sub="MAE — Mean absolute error"
                        plain="On average, how far off the model's score is from the weighted formula. Lower is better."
                      />
                      <StatCard
                        label="Big Miss Penalty"
                        value={metricsResult.regression.rmse.toFixed(4)}
                        sub="RMSE — Root mean squared error"
                        plain="Like average error but penalises large misses more heavily. Lower is better."
                      />
                      <StatCard
                        label="Trend Match"
                        value={metricsResult.regression.pearson_r.toFixed(4)}
                        sub="Pearson r — Linear alignment"
                        plain="When the formula score goes up, does the model score go up proportionally? 1.0 = perfect."
                      />
                      <StatCard
                        label="Ranking Match"
                        value={metricsResult.regression.spearman_rho.toFixed(4)}
                        sub="Spearman ρ — Rank alignment"
                        plain="Do the model and formula agree on the ranking order? 1.0 = identical ordering."
                      />
                    </SimpleGrid>

                    <Card shadow="sm" radius="lg" style={{ border: '1px solid #f1f1f1' }}>
                      <Text fw={500} mb={4} style={{ color: '#111' }}>Calibration — Mean Model Output per Score Decile</Text>
                      <Text size="xs" c="dimmed" mb="md">
                        For each bucket of the weighted formula score, what does the model output on average?
                      </Text>
                      <Table striped highlightOnHover>
                        <Table.Thead>
                          <Table.Tr>
                            <Table.Th>Formula Score Range</Table.Th>
                            <Table.Th style={{ textAlign: 'right' }}>Pairs</Table.Th>
                            <Table.Th style={{ textAlign: 'right' }}>Model Output (avg)</Table.Th>
                          </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                          {metricsResult.regression.calibration.map((row) => (
                            <Table.Tr key={row.range}>
                              <Table.Td style={{ fontFamily: 'monospace' }}>{row.range}</Table.Td>
                              <Table.Td style={{ textAlign: 'right' }}>{row.n_pairs.toLocaleString()}</Table.Td>
                              <Table.Td style={{ textAlign: 'right' }}>
                                {row.mean_pred != null ? row.mean_pred.toFixed(4) : '—'}
                              </Table.Td>
                            </Table.Tr>
                          ))}
                        </Table.Tbody>
                      </Table>
                    </Card>
                  </Stack>
                ) : (
                  <Alert color="yellow" radius="lg">
                    Regression metrics unavailable — regenerate the dataset to include raw_scores.
                  </Alert>
                )}

                <Divider />

                {/* Binary metrics */}
                <Stack gap="lg">
                  <div>
                    <Title order={3} style={{ color: '#111', fontWeight: 500 }} mb={4}>
                      Binary Metrics
                    </Title>
                    <Text size="sm" c="dimmed">Classification performance against the 0/1 training labels (reference only)</Text>
                  </div>
                  <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="lg">
                    <StatCard
                      label="AUC-ROC"
                      value={metricsResult.binary.auc_roc.toFixed(4)}
                      sub="Discrimination"
                      plain="How well the model separates good matches from bad ones. 1.0 = perfect, 0.5 = random."
                    />
                    <StatCard
                      label="Accuracy"
                      value={(metricsResult.binary.accuracy * 100).toFixed(1) + '%'}
                      sub="At 0.5 threshold"
                      plain="Fraction of pairs correctly called a match or non-match at the 0.5 cutoff."
                    />
                    <StatCard
                      label="Mean pred (pos)"
                      value={metricsResult.binary.mean_pred_pos.toFixed(4)}
                      sub="True matches"
                      plain="Average score the model gives to good-match pairs. Should be close to 1."
                    />
                    <StatCard
                      label="Mean pred (neg)"
                      value={metricsResult.binary.mean_pred_neg.toFixed(4)}
                      sub="True non-matches"
                      plain="Average score the model gives to bad-match pairs. Should be close to 0."
                    />
                  </SimpleGrid>
                  <Card shadow="sm" radius="lg" style={{ border: '1px solid #f1f1f1', padding: '1.5rem', maxWidth: 400 }}>
                    <Text size="sm" c="dimmed" mb={4}>Pos - Neg separation</Text>
                    <Text fw={600} style={{ fontSize: '1.75rem', color: '#20c997', lineHeight: 1 }}>
                      {metricsResult.binary.delta.toFixed(4)}
                    </Text>
                    <Text size="xs" mt={8} style={{ color: '#555', borderTop: '1px solid #f1f1f1', paddingTop: 8, lineHeight: 1.4 }}>
                      Gap between model scores on good vs bad matches. Larger = more confident separation.
                    </Text>
                  </Card>
                </Stack>
              </Stack>
            )}
          </Stack>
        )}

      </Container>
    </Box>
  );
}
