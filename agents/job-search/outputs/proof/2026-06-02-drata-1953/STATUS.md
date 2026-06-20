BLOCKED — 2026-05-26T05:50:00+00:00 — browser-tool-stolen-focus + popup-ad-tab

role_id: 635
ats: ashby (Drata tenant)
url: https://jobs.ashbyhq.com/drata/d167dbcd-a66f-4b9f-be19-cdc38e4bc756

Real attempt this session. Filled all 6 text fields successfully on first navigate (name, preferred-name, email, phone, location, linkedin). Hit issue mid-flow on Y/N clicks: the Drata Ashby page (or its embedded ad/captcha infra) appears to spawn a `window.open(youtube-transcript.io/videos?id=AQGM2TlZqtU)` popup tab. Once that popup exists, the OpenClaw browser tool's per-call `targetId=` parameter is ignored — every subsequent `act:evaluate` / `act:clickCoords` runs against the youtube-transcript.io tab instead of the Drata tab, even when explicit `focus` is called first.

Reproduction:
1. Cleared user-data dir entirely (rm -rf user-data, fresh Chrome start). 
2. Fresh navigate to Drata application URL → Drata tab loads cleanly (only Drata + recaptcha iframe in tabs list).
3. First eval call (block window.open or fill text) lands on a NEW tab `youtube-transcript.io/videos?id=AQGM2TlZqtU` that appears DURING the eval — proving the popup is opened by the Drata page itself on load.
4. Browser tool returns content from the new tab regardless of `targetId=<drata-id>`. `focus` action returns ok but next eval still hits the wrong tab.

Recovery attempts:
- `browser:close` of the youtube tab: tab persists in `tabs` list.
- `browser:focus` of Drata tab: brief success, then immediately re-stolen.
- Multiple browser stop/start + user-data wipe + window.open shimming: popup re-appears on every fresh load.

Form-fill itself works (verified on first attempt before tab-steal — 6/6 text inputs filled cleanly via JS native-value-setter). Resume + EEO + Y/N flow could not be completed because the browser tool can't keep focus on the right tab.

Status of prior blocker (captcha): unconfirmed this session (couldn't reach submit). Prior worker reported Drata Ashby score-gate blocked, 2 attempts — that's still likely the deeper blocker even if the popup-tab issue is fixed.

Prep packet ready — Cyrus can submit manually from his residential browser.

agent_notes: "BLOCKED 2026-05-26: browser-tool tab-focus stolen by youtube-transcript popunder injected on page load — Drata Ashby page spawns popup that takes over browser-tool targetId, prevents serial form-fill | also likely captcha-gated underneath (see prior 2-attempt note)"
