# Threat model

## Protected against

- accidental file edits after sealing;
- accidental deletion of a sealed file;
- transfer corruption;
- a changed report or generated difference image inside a bundle;
- omitted, extra, or duplicate ZIP members;
- ZIP path traversal and backslash-based path ambiguity;
- a stale seal after `case.json` changes;
- silent replacement of an existing phase and slot during import.

## Not protected against

- a dishonest person editing an image before its first seal;
- forged EXIF metadata;
- a compromised computer or Python runtime;
- deletion and recreation of an entire case plus seal;
- proof of when the seal existed;
- identity, signature, or trusted timestamp verification;
- semantic image forgery detection;
- legal interpretation.

## Trust model

SHA-256 provides byte identity, not provenance. The verifier is most useful when the seal root or bundle hash is also stored through a separate channel, such as an email already sent to both parties, a versioned repository, a trusted timestamp service, or another independently retained record.

RoomReceipt does not currently implement signatures or RFC 3161 timestamps. A future implementation must keep those optional and must never label a local clock as a trusted timestamp.

## Privacy

The case can contain address data, interior images, personal objects, EXIF identifiers, and GPS metadata in original files. The HTML report does not print GPS coordinates, but originals remain in the case and bundle.

Review every report and bundle before sharing. Store originals and bundles with access controls appropriate to the sensitivity of the property and people shown.
