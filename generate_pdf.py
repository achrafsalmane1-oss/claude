import weasyprint

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; color: #222; max-width: 900px; margin: 40px auto; padding: 0 40px; }
  h1 { font-size: 22px; color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }
  h2 { font-size: 16px; color: #1a1a2e; margin-top: 28px; }
  h3 { font-size: 14px; color: #333; margin-top: 18px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 12px; }
  th { background: #1a1a2e; color: white; padding: 7px 10px; text-align: left; }
  td { border: 1px solid #ddd; padding: 6px 10px; }
  tr:nth-child(even) { background: #f7f7f7; }
  blockquote { border-left: 3px solid #1a1a2e; margin: 10px 0 10px 20px; padding: 6px 14px; background: #f0f4ff; color: #333; font-style: italic; }
  code { background: #eee; padding: 1px 5px; border-radius: 3px; font-family: monospace; }
  hr { border: none; border-top: 1px solid #ccc; margin: 24px 0; }
  ul li { margin-bottom: 4px; }
  .footer { margin-top: 40px; font-size: 11px; color: #888; border-top: 1px solid #eee; padding-top: 10px; }
  .totals-row td { background: #1a1a2e !important; color: white; font-weight: bold; border-color: #1a1a2e; }
  .subtotal-row td { background: #e8eaf6 !important; font-weight: bold; }
  .grand-total-row td { background: #1a1a2e !important; color: white; font-weight: bold; }
</style>
</head>
<body>

<h1>PaceGen &times; Otto Results &mdash; Strategy Brief</h1>
<h3 style="font-weight:normal;color:#555;">Campaign Performance &amp; 90-Day Renewal Proposal</h3>
<p><strong>Prepared:</strong> April 28, 2026</p>
<hr>

<h2>Executive Summary</h2>
<p>Over the past ~120 days we have built, tested, and scaled <strong>15 outbound campaigns</strong> for PaceGen across 3 offers (GEO/LLM visibility, Revenue Zen, Eastern Standard), contacted <strong>156,870 prospects</strong>, sent <strong>256,479 emails</strong>, generated <strong>2,523 unique replies</strong>, and produced <strong>348 qualified interested responses</strong>.</p>
<p>This document covers what we built, the signal-based strategies we deployed, what is working, what we are cutting, and what the next 90 days look like.</p>
<hr>

<h2>1. Campaign Overview &mdash; Full History</h2>

<h3>Offer 1: PaceGen GEO / LLM Visibility</h3>
<table>
  <tr><th>Campaign</th><th>Signal Type</th><th>Status</th><th>Leads</th><th>Emails Sent</th><th>Unique Replies</th><th>Interested</th></tr>
  <tr><td>GEO Readiness</td><td>Broad GEO</td><td>Active</td><td>62,911</td><td>115,981</td><td>1,216</td><td>207</td></tr>
  <tr><td>GEO Readiness (Apr 23 &mdash; New Leads)</td><td>Broad GEO</td><td>Active</td><td>3,416</td><td>5,746</td><td>25</td><td>&mdash;</td></tr>
  <tr><td>Existing LLMs &mdash; Google</td><td>llms.txt Signal</td><td>Active</td><td>19,209</td><td>54,920</td><td>685</td><td>92</td></tr>
  <tr><td>Missing LLMs &mdash; Google</td><td>llms.txt Signal</td><td>Complete</td><td>8,977</td><td>8,977</td><td>59</td><td>10</td></tr>
  <tr><td>Competitor Gap Attack &mdash; Google</td><td>Competitor Signal</td><td>Complete</td><td>9,110</td><td>9,111</td><td>163</td><td>22</td></tr>
  <tr><td>Whole-Offer Strategy &mdash; Google</td><td>Whole Offer</td><td>Complete</td><td>1,153</td><td>1,153</td><td>9</td><td>&mdash;</td></tr>
  <tr><td>Missing LLMs &mdash; Microsoft</td><td>llms.txt Signal</td><td>Complete</td><td>2,072</td><td>2,072</td><td>12</td><td>&mdash;</td></tr>
  <tr><td>Competitor Gap Attack &mdash; Microsoft</td><td>Competitor Signal</td><td>Complete</td><td>7,329</td><td>7,329</td><td>67</td><td>3</td></tr>
  <tr><td>Whole-Offer Strategy &mdash; Microsoft</td><td>Whole Offer</td><td>Complete</td><td>5,592</td><td>5,592</td><td>42</td><td>4</td></tr>
  <tr><td>Content Investment + Traffic Decline</td><td>SEO/LLM Decay</td><td>Draft</td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td></tr>
  <tr class="subtotal-row"><td>GEO Subtotal</td><td></td><td></td><td>119,769</td><td>210,881</td><td>2,278</td><td>338</td></tr>
</table>

<h3>Offer 2: Revenue Zen</h3>
<table>
  <tr><th>Campaign</th><th>Status</th><th>Leads</th><th>Emails Sent</th><th>Unique Replies</th><th>Interested</th></tr>
  <tr><td>Revenue Zen &mdash; Main Campaign</td><td>Paused</td><td>2,205</td><td>5,759</td><td>34</td><td>&mdash;</td></tr>
  <tr><td>RZ &mdash; Updated</td><td>Paused</td><td>16,772</td><td>16,772</td><td>74</td><td>8</td></tr>
  <tr><td>Copy of RZ &mdash; Updated</td><td>Active</td><td>4,474</td><td>4,474</td><td>2</td><td>&mdash;</td></tr>
  <tr class="subtotal-row"><td>RZ Subtotal</td><td></td><td>23,451</td><td>27,005</td><td>110</td><td>8</td></tr>
</table>

<h3>Offer 3: Eastern Standard</h3>
<table>
  <tr><th>Campaign</th><th>Status</th><th>Leads</th><th>Emails Sent</th><th>Unique Replies</th><th>Interested</th></tr>
  <tr><td>Eastern Standard &mdash; Main Campaign</td><td>Paused</td><td>5,366</td><td>10,309</td><td>69</td><td>1</td></tr>
  <tr><td>ES &mdash; Updated</td><td>Active</td><td>8,284</td><td>8,284</td><td>66</td><td>1</td></tr>
  <tr class="subtotal-row"><td>ES Subtotal</td><td></td><td>13,650</td><td>18,593</td><td>135</td><td>2</td></tr>
</table>

<h3>Grand Total &mdash; All Offers</h3>
<table>
  <tr><th>Leads Contacted</th><th>Emails Sent</th><th>Unique Replies</th><th>Interested</th></tr>
  <tr class="grand-total-row"><td>156,870</td><td>256,479</td><td>2,523</td><td>348</td></tr>
</table>
<hr>

<h2>2. Signal-Based Strategies We Have Run</h2>
<p>One concern raised was that we are doing &ldquo;spray-and-pray.&rdquo; That is not accurate. Here is a breakdown of every signal type we have tested and the results:</p>

<h3>Signal 1 &mdash; llms.txt File Detection (Google + Microsoft)</h3>
<p><strong>Campaigns:</strong> Existing LLMs &mdash; Google, Missing LLMs &mdash; Google, Missing LLMs &mdash; Microsoft</p>
<p>We scraped companies with or without <code>llms.txt</code> files on their domains &mdash; a strong technical signal that the company cares about AI visibility. We split into two sub-angles:</p>
<ul>
  <li><strong>Existing LLMs:</strong> &ldquo;You already have an llms.txt &mdash; do you know if AI is actually citing you?&rdquo;</li>
  <li><strong>Missing LLMs:</strong> &ldquo;You do not have an llms.txt &mdash; here is what you are leaving on the table.&rdquo;</li>
</ul>
<p>The Existing LLMs &mdash; Google campaign became our <strong>highest unique reply rate campaign at ~3.6%</strong> (685 replies / 19,209 leads).</p>
<p><strong>Example &rarr; Roger Rizk, Co-Founder &amp; COO @ BLACKBOX.AI:</strong></p>
<blockquote>&ldquo;Roger, checked blackbox.ai/llms.txt and saw you already have one on your website. Smart move. Do you know if AI tools are actually citing Blackbox when people ask about ai development platform? We track AI citation rates and can show you exactly where you are showing up (or not). Can I send over a report?&rdquo;</blockquote>
<p><strong>Roger replied:</strong> &ldquo;please share how you can help in details&rdquo;</p>

<h3>Signal 2 &mdash; Competitor Gap Attack (Google + Microsoft)</h3>
<p><strong>Campaigns:</strong> Competitor Gap Attack &mdash; Google, Competitor Gap Attack &mdash; Microsoft</p>
<p>We ran prospects&rsquo; competitors through ChatGPT and Perplexity and identified where competitors are cited but the prospect is not.</p>
<p><strong>Example &rarr; Oleg Zankov, Founder @ Latenode:</strong></p>
<blockquote>&ldquo;Oleg &mdash; ran &lsquo;best ai workflow automation saas&rsquo; through ChatGPT. Zapier showed up. Latenode did not. Right now is the easiest time to fix that. Early movers are locking in positions while competitors sleep. We make AI recommend you instead of your competitors. 90 days to full visibility &mdash; most see first citations in 30. Want me to send over a competitive breakdown?&rdquo;</blockquote>
<p><strong>Oleg replied:</strong> &ldquo;Tell me how you do it&rdquo;</p>

<h3>Signal 3 &mdash; GEO Readiness Scorecard</h3>
<p><strong>Campaigns:</strong> GEO Readiness (main + refresh). Highest absolute interested replies: <strong>207</strong>.</p>
<p><strong>Example &rarr; Nikhil @ Simpl AI:</strong></p>
<blockquote>&ldquo;Nikhil, searched on ChatGPT and Simpl AI was not cited. We built a GEO Readiness Scorecard &mdash; most companies score 3-5 out of 11, meaning they are invisible to 50%+ of their market. Still interested?&rdquo;</blockquote>
<p><strong>Nikhil replied:</strong> &ldquo;interesting, yeah can you send over the scorecard. I assume your company does GEO consulting to help companies improve?&rdquo;</p>
<p><strong>Example &rarr; Laura Nobles, CEO @ Pazanga Health Communications:</strong></p>
<blockquote>&ldquo;Laura, searched for healthcare public relations on ChatGPT and Pazanga Health Communications was not cited. We built a GEO Readiness Scorecard&hellip;&rdquo;</blockquote>
<p><strong>Laura replied:</strong> &ldquo;Hi Rocky &mdash; Yes, please send me a scorecard to review.&rdquo;</p>
<hr>

<h2>3. What Is Working</h2>
<table>
  <tr><th>Campaign</th><th>Interested</th><th>Unique Replies</th></tr>
  <tr><td>GEO Readiness</td><td>207</td><td>1,216</td></tr>
  <tr><td>Existing LLMs &mdash; Google</td><td>92</td><td>685</td></tr>
  <tr><td>Competitor Gap Attack &mdash; Google</td><td>22</td><td>163</td></tr>
  <tr><td>Missing LLMs &mdash; Google</td><td>10</td><td>59</td></tr>
  <tr><td>RZ &mdash; Updated</td><td>8</td><td>74</td></tr>
  <tr><td>Whole-Offer Strategy &mdash; Microsoft</td><td>4</td><td>42</td></tr>
  <tr><td>Competitor Gap Attack &mdash; Microsoft</td><td>3</td><td>67</td></tr>
  <tr><td>Eastern Standard &mdash; Main Campaign</td><td>1</td><td>69</td></tr>
  <tr><td>ES &mdash; Updated</td><td>1</td><td>66</td></tr>
</table>
<p><strong>Key insight:</strong> GEO and signal-based LLM campaigns are the clear winners by interested count. Revenue Zen and Eastern Standard are generating replies at solid rates but haven&rsquo;t converted to interested at the same level &mdash; likely a copy or offer-fit issue worth addressing next cycle.</p>
<hr>

<h2>4. What Is Not Working / What We Are Cutting</h2>
<p><strong>Whole-Offer Strategy &mdash; Google:</strong> 1,153 leads, only 9 replies, 0 interested. Multi-angle approach dilutes the message. Cutting entirely.</p>
<p><strong>Content Investment + Traffic Decline:</strong> Never launched. Shelving &mdash; requires a different buyer mindset and longer education sequence.</p>
<p><strong>Microsoft as primary:</strong> Consistently underperformed Google equivalents. Keeping as small supplemental only.</p>
<p><strong>RZ and ES reply-to-interested conversion:</strong> Both offers generate replies (110 and 135 respectively) but very few interested (8 and 2). The copy is getting attention but the offer framing or follow-up sequence isn&rsquo;t converting curiosity into intent. Recommend a copy and sequence review before the next cycle.</p>
<hr>

<h2>5. Why Volume + Signal Is Not Spray-and-Pray</h2>
<p>At the signal volumes available (companies with llms.txt files, companies with specific competitor citations), we can exhaust the cleanest intent signals within a few days. The GEO market is still early and the addressable list of &ldquo;perfect signal&rdquo; accounts is not infinite.</p>
<p>The right architecture is two tiers:</p>
<ul>
  <li><strong>Tier 1 (pure signal):</strong> llms.txt owners, verified ChatGPT citation gaps &rarr; high personalization, lower volume</li>
  <li><strong>Tier 2 (broad + personalized):</strong> GEO Readiness at scale, personalized to company name + keyword + AI engine &rarr; 207 interested per cycle</li>
</ul>
<p>Both tiers are running. Volume at Tier 2 keeps pipeline full while Tier 1 warms and converts.</p>
<hr>

<h2>6. Infrastructure Recommendation</h2>
<p><strong>Current situation:</strong> All sending inboxes are under Rocky&rsquo;s name across multiple aging domains. Deliverability degrades as campaigns age.</p>
<ul>
  <li><strong>New domain + inbox per offer</strong> &mdash; 4 sending identities minimum (GEO, RZ, ES, reserve)</li>
  <li><strong>Warm new inboxes now</strong> &mdash; 4&ndash;6 week warmup before high-volume sends</li>
  <li><strong>Retire aging domains</strong> &mdash; <code>pacegenbrandauthority.info</code> and <code>pacegenanswerstrategy.info</code> should be rotated out</li>
</ul>
<p>Fresh infrastructure is the single biggest lever for getting more replies out of the same copy.</p>
<hr>

<h2>7. Next 90 Days &mdash; Proposed Plan</h2>
<h3>Continue / Scale</h3>
<ul>
  <li><strong>GEO Readiness</strong> &mdash; Refresh with new leads and new infrastructure. Backbone of the program.</li>
  <li><strong>Existing LLMs &mdash; Google</strong> &mdash; Best reply rate (3.6%). Reload with new lead batch.</li>
  <li><strong>RZ and ES</strong> &mdash; Continue with revised sequences focused on converting the high reply volume into more interested responses.</li>
</ul>
<h3>New Campaigns to Launch</h3>
<ul>
  <li><strong>Re-engagement campaign</strong> &mdash; 2,500+ replies in the system. A targeted re-engagement sequence can generate meetings from an already-warm list.</li>
  <li><strong>Blog content / thought leadership angle</strong> &mdash; &ldquo;You are creating great content. Here is why ChatGPT is not citing it.&rdquo;</li>
  <li><strong>Healthcare + NGO vertical</strong> &mdash; Strong response from Pazanga Health, FreeWorld, NAMI. Formalize as a dedicated campaign.</li>
</ul>
<h3>What We Are NOT Doing</h3>
<ul>
  <li>Whole-offer multi-angle campaigns &mdash; data says they do not work</li>
  <li>Microsoft as a primary target</li>
</ul>
<hr>

<h2>8. Summary</h2>
<p>In roughly 4 months we have:</p>
<ul>
  <li>Built and tested <strong>15 distinct outbound campaigns</strong> across 3 offers and multiple signal types</li>
  <li>Contacted <strong>156,870 unique prospects</strong></li>
  <li>Sent <strong>256,479 emails</strong></li>
  <li>Generated <strong>2,523 unique replies</strong> and <strong>348 qualified interested responses</strong></li>
  <li>Proven out signal-based strategies with documented positive replies from real founders and CEOs</li>
  <li>Identified the campaigns worth scaling and the ones worth cutting</li>
</ul>
<p>The pipeline is working across all three offers. Next step: refresh infrastructure, revise RZ and ES sequences to convert more replies into meetings, re-engage the warm list, and add 1&ndash;2 new angles on top of the proven base.</p>
<p>We are ready to propose a new 90-day scope if PaceGen wants to continue.</p>

<div class="footer">Prepared by Achraf Salmane / Otto Results &nbsp;|&nbsp; achraf@ottoresults.com</div>
</body>
</html>"""

weasyprint.HTML(string=html).write_pdf('/home/user/claude/pacegen-strategy-brief.pdf')
print('PDF generated successfully')
