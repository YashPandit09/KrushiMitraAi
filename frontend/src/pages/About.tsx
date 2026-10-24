export default function About() {
  return (
    <div className="prose">
      <div className="page-head">
        <div className="eyebrow">About</div>
        <h1>About KrushiMitra AI</h1>
        <p>
          An open, reproducible system for district-level Kharif rice yield outlooks in Odisha - built on public data,
          evaluated honestly, and free to run anywhere.
        </p>
      </div>

      <section className="card">
        <h2>Where it started</h2>
        <p>
          KrushiMitra AI began as our team's entry to <strong>Smart India Hackathon 2025</strong>, problem statement{" "}
          <strong>SIH25044 - "AI-Powered Crop Yield Prediction and Optimization"</strong>, set by the Government of
          Odisha. The hackathon prototype (also known as KrushiBandhu AI / Yield-Ai) is at{" "}
          <a href="https://github.com/Shaunakrane914/Yield-Ai">github.com/Shaunakrane914/Yield-Ai</a>.
        </p>
        <p>
          Thanks to the SIH 2025 team, including Shaunak Rane and Yash Pandit, for the original idea, the problem
          framing and the first prototype. See CREDITS.md in the repository for the full acknowledgements.
        </p>
        <p>
          This repository is a ground-up rebuild. It replaces the prototype's placeholder data with official statistics
          and real weather, and adds out-of-sample evaluation, calibrated uncertainty and a secure, deployable
          application. No code from the prototype is reused.
        </p>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Open source</h2>
        <p>
          Code is released under the MIT licence. Data files keep their original licences (DES/UPAg via the India Data
          Portal: ODC-By; geoBoundaries: ODbL; NASA POWER and NOAA IBTrACS: public; Open-Meteo: CC BY 4.0). Source and
          documentation: <a href="https://github.com/YashPandit09/KrushiMitraAi">github.com/YashPandit09/KrushiMitraAi</a>.
        </p>
        <p>
          Found a security problem? Please report it privately through the repository's security advisories rather than
          a public issue.
        </p>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Disclaimer</h2>
        <p>
          Forecasts are statistical estimates with stated uncertainty. They are not official statistics and not
          agronomic, financial or insurance advice. For farm decisions, contact your local agriculture extension officer
          or the Department of Agriculture & Farmers' Empowerment, Government of Odisha.
        </p>
      </section>
    </div>
  );
}
