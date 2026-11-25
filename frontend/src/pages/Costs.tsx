import { api } from "../api";
import { ErrorNote, PageTitle, money, usePolled, words } from "../ui";

export function Costs() {
  const { data, error } = usePolled(api.costs, [], 8000);
  const reference = data?.photoshoot_reference;

  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <PageTitle>Costs</PageTitle>
          <p>Every generation is counted, including failed attempts and retries.</p>
        </div>
      </div>
      <ErrorNote message={error} />
      {data && (
        <>
          <dl className="cost-line">
            <div>
              <dt>Cost per accepted photo</dt>
              <dd>{money(data.usd_per_accepted)}</dd>
            </div>
            <div>
              <dt>Total spent</dt>
              <dd>{money(data.total_usd)}</dd>
            </div>
            <div>
              <dt>Accepted photos</dt>
              <dd>{data.accepted_images}</dd>
            </div>
            <div>
              <dt>Cost per garment</dt>
              <dd>{money(data.usd_per_product)}</dd>
            </div>
          </dl>

          {reference && (
            <p className="compare-note">
              For comparison, one traditional photoshoot is estimated at ${reference.low.toLocaleString()} to $
              {reference.high.toLocaleString()}. This is a rough estimate from the project brief, not a measured quote.
            </p>
          )}

          <h2 className="section-title">By garment</h2>
          {data.by_product.length === 0 ? (
            <p className="muted">Costs appear here after your first photoshoot.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Garment</th>
                    <th scope="col" className="num">Accepted</th>
                    <th scope="col" className="num">Spent</th>
                    <th scope="col" className="num">Per accepted</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_product.map((p) => (
                    <tr key={p.id}>
                      <td><b className="cell-title">{p.sku}</b> <span className="cell-sub">{p.name}</span></td>
                      <td className="num">{p.accepted}</td>
                      <td className="num">{money(p.usd)}</td>
                      <td className="num">{p.accepted ? money(p.usd / p.accepted) : "None"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.by_operation.length > 0 && (
            <>
              <h2 className="section-title">By step</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Step</th>
                      <th scope="col" className="num">Calls</th>
                      <th scope="col" className="num">Spent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_operation.map((o) => (
                      <tr key={o.operation}>
                        <td>{o.operation === "dress" ? "Garment photos" : o.operation === "judge" ? "Vision checks (estimated)" : o.operation === "shot" ? "Model shots" : words(o.operation)}</td>
                        <td className="num">{o.calls}</td>
                        <td className="num">{money(o.usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
