import './Footer.scss'

export function Footer() {
  return (
    <footer className="sw-footer">
      <p>
        Built from public GitHub data and the Stellar ledger archive. Proposals come from the data,
        not a wish list, and scores count distinct owners so copies of one template do not inflate
        demand. Every figure here links back to its evidence.
      </p>
      <p className="sw-footer-small">
        State of Soroban is a research index. Scores are a ranked shortlist, read the evidence
        before acting on one.
      </p>
    </footer>
  )
}
