/** Source closure must refer to this exact input snapshot and a finished past month. */
export function periodCoverage(months, evidence = {}, { inputDigest, asOf } = {}) {
  return Object.fromEntries([...new Set([...months, ...Object.keys(evidence.periods || {}).filter(m => /^\d{4}-(0[1-9]|1[0-2])$/.test(m))])].sort().map(month => {
    const proof = evidence.periods?.[month];
    const complete = proof?.status === "complete" && proof.sourceClosed === true && proof.paginationComplete === true
      && typeof proof.evidence === "string" && proof.evidence.trim().length > 0
      && proof.inputDigest === inputDigest && month < asOf.slice(0, 7);
    return [month, { status: complete ? "complete" : "partial", reason: complete ? "source_closure_confirmed" : "source_closure_unconfirmed", evidence: complete ? proof.evidence : null }];
  }));
}
export function commonCompleteMonths(years, coverage) {
  return Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"))
    .filter(month => years.every(year => coverage[`${year}-${month}`]?.status === "complete"));
}
