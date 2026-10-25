import { Compass, PlayCircle } from "lucide-react";
import { useTour } from "../tour/TourProvider";

export default function Home() {
  const tour = useTour();
  return (
    <section className="landing">
      <div className="landing-copy">
        <div className="kicker">Lost fishing gear · North Pacific pilot</div>
        <h1>Lost nets keep killing for years. We help bring them back.</h1>
        <p className="lede">A fishing net lost at sea keeps drifting and catching: seals, turtles, seabirds, coral. This system gives every net an identity,
          forecasts where lost nets drift, and pays recovery crews automatically once a recovery is verified.</p>
        <div className="pillars">
          <div><b>An owner</b><span>Every net registered at sale, with a QR tag and a refundable deposit</span></div>
          <div><b>A location</b><span>Drift forecasts on real ocean-current data</span></div>
          <div><b>A price</b><span>A recovery reward, paid automatically by a smart contract</span></div>
        </div>
        <div className="entry">
          <button className="btn primary lg" onClick={tour.start}><PlayCircle size={18} />Start guided demo</button>
          <a className="btn lg" href="#/explore"><Compass size={18} />Explore independently</a>
        </div>
        <p className="entry-note">The guided demo follows one net from purchase to a paid recovery in about four minutes, using the live system.
          Starting it restores the shared demo world to its starting point.</p>
        <div className="facts">
          <div><b>46%</b><span>of the Great Pacific Garbage Patch, by weight, is fishing nets</span></div>
          <div><b>~2%</b><span>of all fishing gear in use is lost every year</span></div>
          <div><b>96 tons</b><span>of nets removed from Hawaii's remote reefs in 2024</span></div>
        </div>
      </div>
      <figure className="landing-visual" style={{ margin: 0 }}>
        <img src="/img/monk-seal-net.jpg" alt="A Hawaiian monk seal with fishing net wrapped around its neck on a beach" />
        <figcaption><b>A Hawaiian monk seal caught in a derelict net.</b>Papahānaumokuākea Marine National Monument, where the North Pacific's currents carry lost gear. Photo: NOAA Fisheries (public domain).</figcaption>
      </figure>
    </section>
  );
}
