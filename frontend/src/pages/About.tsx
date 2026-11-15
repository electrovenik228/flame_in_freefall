import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Card, ExternalA, PageHeader, SectionTitle } from "@/components/ui";

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      <Card className="space-y-3 text-[0.95rem] leading-relaxed [&_li]:ml-5 [&_li]:list-disc [&_ul]:space-y-1.5">{children}</Card>
    </section>
  );
}

export default function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="About and method" lead="Where the data comes from, how the ranking works, what the AI does and does not do, and how to cite." />

      <Block title="Not a safety authority">
        <p>
          Flame in Freefall is a research aid. It does not replace NASA flammability standards or testing, and its rankings are not safety
          ratings. The site is an independent project and is not endorsed by NASA.
        </p>
      </Block>

      <Block title="Data sources">
        <ul>
          <li>
            <ExternalA href="https://psi.nasa.gov/physci/repo/search?q=combustion&data_source=psi&data_type=investigation">NASA Physical Sciences Informatics (PSI)</ExternalA>{" "}
            is the single source of experimental facts: investigation records, experiment tables and publication lists.
          </li>
          <li>The catalogue holds the Combustion Science records of PSI. Each record page links back to PSI and shows its DOI.</li>
          <li>Test runs are parsed from the experiment tables of FLEX, ACME CFI-G, BASS-II and Saffire-I, -II and -III. The original row is kept beside every normalized value, with its file and row number.</li>
          <li>A missing value stays missing. It is never replaced with zero or an estimate. Units are fixed: oxygen in percent by volume, pressure in kPa (psi shown beside it), flow in cm/s.</li>
          <li>Raw data, telemetry, images and video are not copied. The site links to PSI for them.</li>
          <li>Crew environments use the values of the challenge brief and NASA&rsquo;s standard atmospheres. The Mars habitat uses the exploration atmosphere of 8.2 psia and 34% oxygen (<ExternalA href="https://ntrs.nasa.gov/citations/20150021491">NASA evidence report</ExternalA>).</li>
        </ul>
      </Block>

      <Block title="Scoring rubric">
        <p>The relevance score is a weighted rubric, not a black box. You can change the weights on the <Link to="/ranking" className="text-accent hover:underline">ranking page</Link>.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr><th scope="col" className="pb-2 pr-3 font-medium">Criterion</th><th scope="col" className="pb-2 pr-3 text-right font-medium">Weight</th><th scope="col" className="pb-2 pr-3 font-medium">Scored by</th><th scope="col" className="pb-2 font-medium">How</th></tr>
            </thead>
            <tbody className="[&_td]:border-t [&_td]:border-line/60 [&_td]:py-2 [&_td]:pr-3 [&_td]:align-top">
              <tr><td>Atmosphere match</td><td className="num text-right">30</td><td>Code</td><td>A tested condition within 1 percentage point of oxygen and 5 kPa of the environment scores 100%. Beyond that the score falls in a straight line to 0 at a further 10 points of oxygen or 50 kPa. Test runs are used when the record has them, otherwise the ranges stated in the record.</td></tr>
              <tr><td>Fuel and material relevance</td><td className="num text-right">25</td><td>AI, once per record</td><td>How close the tested fuels are to crew-cabin materials, scored 0 to 10 against written anchors, with quoted evidence.</td></tr>
              <tr><td>Safety function</td><td className="num text-right">20</td><td>AI, once per record</td><td>How directly the results serve prevention, detection or suppression, scored 0 to 10, with quoted evidence.</td></tr>
              <tr><td>Flow match</td><td className="num text-right">15</td><td>Code</td><td>Scored only when the environment has a flow window, within 2 cm/s, then falling to 0 over 20 cm/s. The challenge brief gives no ventilation speed for the reference environments, so it is scored for custom atmospheres only.</td></tr>
              <tr><td>Gravity relevance</td><td className="num text-right">10</td><td>Code</td><td>6 points for microgravity data, 2 more when the record refers to 1 g reference tests, 2 more for a partial-gravity proxy such as an electric field.</td></tr>
            </tbody>
          </table>
        </div>
        <ul>
          <li>A criterion without data is marked &ldquo;not available&rdquo;. The total is rescaled over the remaining criteria and the row carries a &ldquo;partial data&rdquo; tag. A missing value never counts as zero.</li>
          <li>Data depth is not part of the score. It is shown as a badge and a filter.</li>
          <li>PSI holds no partial-gravity data. Rankings for the Moon and Mars differ only through the atmosphere criterion.</li>
        </ul>
      </Block>

      <Block title="AI disclosure">
        <ul>
          <li>AI text is written by Claude models from Anthropic, working only from records stored in this site&rsquo;s database. It is labelled &ldquo;AI-generated&rdquo; with its model and date.</li>
          <li>Summaries and assistant answers carry numbered citations that open the source passage and the PSI link.</li>
          <li>Attributes read from record text (fuel state, safety function, condition ranges, sensors) are stored with an exact quote. A program checks that every quote appears word for word in the source and rejects the result if one does not.</li>
          <li>Numbers in AI text are checked against the cited record. Stored text that fails is not published. A streamed answer shows a mark when its numbers check out, or a flag on any number that does not.</li>
          <li>No number on a chart or in a ranking total is written by AI. Unit conversions are done in code.</li>
          <li>AI output is published after these automated checks and is marked &ldquo;not yet reviewed&rdquo; until an expert reviews it.</li>
          <li>A response the model declines to give is never stored or shown.</li>
        </ul>
      </Block>

      <Block title="Limitations">
        <ul>
          <li>Depth varies by investigation. Some records publish test-by-test tables, some only a test matrix, some no table at all. Records without per-test data are described, not charted.</li>
          <li>Condition ranges read from record text may be planned ranges rather than the conditions actually run.</li>
          <li>Phrase matching decides the 1 g reference and electric-field points of the gravity criterion; the matching sentence is shown so you can judge it.</li>
          <li>The site is served over plain HTTP at an IP address. It has no accounts and collects no personal data.</li>
        </ul>
      </Block>

      <Block title="Privacy">
        <p>No account is needed. Assistant conversations are stored for 30 days under an anonymous session ID, without IP addresses, for quality review. You see them only during your browser session.</p>
      </Block>

      <Block title="How to cite">
        <p>Cite the PSI record, not this site: use the DOI shown at the top of each investigation page. PSI records in the catalogue state their licence; most are Creative Commons Zero.</p>
      </Block>
    </div>
  );
}
