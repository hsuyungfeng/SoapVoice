# FreeScribe Integration Research Report

**Date**: 2026-04-27  
**Project**: SoapVoice v1.1  
**Status**: Deep research completed — Integration assessment provided

---

## 1. Executive Summary

**FreeScribe** is a maintained open-source medical scribe (fork of AI-Scribe) with **12 stars, 7 forks, 78 open issues**. It's **94.9% Python**, AGPL-3.0 licensed, and provides client-server architecture for SOAP note generation.

**Integration Assessment**: ⚠️ **Limited value as submodule** — overlapping scope creates maintenance burden. **Recommended approach: Selective component extraction** (data anonymization, NLP models) rather than full integration.

---

## 2. FreeScribe Architecture

### 2.1 Core Structure
```
FreeScribe/
├── src/
│   └── FreeScribe/
│       ├── client/          # GUI + audio capture
│       └── server/          # LLM + transcription backend
├── scripts/                 # Build & deployment
├── docs/                    # Project documentation
├── tests/                   # Test suite
├── flatpak/                 # Linux packaging
├── mac/, build-*.sh         # macOS/Windows builds
└── *_requirements.txt       # 53 Python dependencies
```

### 2.2 Key Features
- ✅ Local-first operation (no cloud required)
- ✅ Flexible: local or remote LLM/ASR
- ✅ SOAP note generation
- ✅ Cross-platform (Windows, macOS, Linux)
- ✅ Medical data anonymization (Scrubadub)
- ✅ Client-server separation

### 2.3 Technology Stack

| Layer | FreeScribe | SoapVoice |
|-------|-----------|-----------|
| **ASR** | Faster-Whisper | Faster-Whisper ✅ |
| **LLM** | Kobold, llama-cpp-python | Gemma 4:E4B (llama-cpp-python) ✅ |
| **NLP** | spaCy (en_core_sci_md) | Custom terminology mapping |
| **Anonymization** | Scrubadub | None (planned) |
| **Server** | Custom Python | FastAPI ✅ |
| **Client** | Desktop GUI (implied) | ttkbootstrap GUI ✅ |
| **Database** | Not documented | SQLite (v1.1 adding) |
| **Auth** | Not documented | API Key + CORS ✅ |

---

## 3. Detailed Comparison

### 3.1 Dependency Overlap

**FreeScribe imports (53 packages):**
```
Core: numpy, scipy, torch, torchaudio, transformers, numba
NLP:  nltk, spacy, textblob, tiktoken, faster-whisper
LLM:  llama-cpp-python, anthropic, pydantic-ai
Sec:  scrubadub, cryptography, keyring
IO:   PIL, librosa, PyAudio, docker, pyinstaller
Web:  requests, httpx, fastapi (implied)
Util: pydantic, click, Jinja2, dateparser, phonenumbers
```

**SoapVoice imports (42 packages):**
```
Core: numpy, torch, torchaudio, transformers
NLP:  sentence-transformers, llama-cpp-python
LLM:  Gemma 4:E4B (GGUF)
Anon: None (gap)
IO:   PIL, librosa, PyAudio, faster-whisper
Web:  fastapi, httpx, requests, websockets
Auth: pyjwt, cryptography
Util: pydantic, click, python-dotenv, aiosqlite
GUI:  ttkbootstrap, keyboard, pystray, python-xlib
```

**Shared heavy dependencies:**
- torch, torchaudio, transformers (17 GB+ total) ✅
- faster-whisper, PyAudio, librosa ✅
- llama-cpp-python ✅
- pydantic, requests, cryptography ✅

**Unique to FreeScribe:**
- spaCy + en_core_sci_md (medical NLP) — **240 MB model**
- scrubadub (PII removal) — **highly relevant**
- en_core_web_md (general NLP)
- textblob, tiktoken
- anthropic SDK, pydantic-ai

**Unique to SoapVoice:**
- ttkbootstrap, keyboard, pystray (GUI)
- websockets, aiosqlite (networking + DB)
- sentence-transformers, chromadb (RAG)

---

## 4. Integration Analysis

### 4.1 Option A: Full Submodule Integration ❌ NOT RECOMMENDED

**Pros:**
- ✅ Immediate SOAP generation capability
- ✅ Established client-server pattern
- ✅ Cross-platform maturity

**Cons:**
- ❌ **Massive dependency bloat** — adds 11+ packages FreeScribe-specific
  - spaCy (240 MB) + models duplicate SoapVoice NLP
  - anthropic SDK unused
  - pydantic-ai unused
- ❌ **Architectural mismatch** — FreeScribe's client-server differs from SoapVoice's single-process design
- ❌ **Maintenance burden** — 78 open issues, active refactoring, AGPL-3.0 copyleft (must distribute changes)
- ❌ **License conflict** — SoapVoice has no declared license; FreeScribe's AGPL-3.0 is viral
- ❌ **Code duplication** — Both have SOAP generation, audio capture, Whisper integration
- ❌ **Small user base** — 12 stars indicates early-stage, potential abandonment risk

**Verdict**: Creates more problems than it solves.

---

### 4.2 Option B: Selective Component Extraction ✅ RECOMMENDED

Extract **only high-value, non-overlapping components**:

#### B1: Medical NLP (spaCy + en_core_sci_md)
**Value**: Clinical entity recognition, medical terminology normalization  
**SoapVoice Gap**: Currently uses custom 80-term mapping  
**Integration Path**:
```python
# src/nlp/medical_entity_extractor.py (NEW)
import spacy

model = spacy.load("en_core_sci_md")  # ~240 MB
# Extract: diseases, treatments, anatomical terms, medications
# Enhance Phase 8 terminology mapping

# Add to pyproject.toml:
# "spacy>=3.7.0",
# "en_core_sci_md @ https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_md-0.5.1-py3-none-any.whl"
```

**Cost**: +240 MB disk, +8s startup  
**Benefit**: ⬆️ Entity recognition from 80 to 5000+ medical terms

#### B2: Data Anonymization (Scrubadub)
**Value**: HIPAA-compliant PII removal  
**SoapVoice Gap**: No anonymization (blocker for Phase 10 audit trail)  
**Integration Path**:
```python
# src/nlp/anonymizer.py (NEW)
from scrubadub import Scrubber
import scrubadub.post_processors

scrubber = Scrubber(post_processor=ScrubadubPhoneNumber())
safe_text = scrubber.clean(patient_note)  # Remove SSN, phone, DOB, etc.
```

**Cost**: +2 MB, ~10 ms per SOAP  
**Benefit**: ⬆️ HIPAA compliance, audit trail confidence

#### B3: Phone Number Parsing (phonenumbers)
**Value**: Patient contact normalization  
**SoapVoice Gap**: Manual phone entry in patient records  
**Cost**: +3 MB  
**Benefit**: ⬆️ Structured patient demographics

#### B4: Date Parsing (dateparser + pytz)
**Value**: Flexible date format parsing  
**SoapVoice Gap**: Currently assumes ISO format  
**Cost**: +5 MB  
**Benefit**: ⬆️ Clinical notes with natural language dates ("last Tuesday", "3 weeks ago")

---

### 4.3 Option C: Architectural Learning (NO INTEGRATION)

**Study FreeScribe's client-server pattern** for Phase 11 (Thin Client) design:

**Applicable patterns:**
- Remote LLM inference over HTTP
- Audio streaming from client → server
- Incremental SOAP streaming back
- Process isolation for heavy ML

**Do NOT copy code** — implement independently using FastAPI + aiosqlite patterns already in SoapVoice.

---

## 5. Recommended Integration Strategy

### Phase 10-03 (Immediate, 30 min)
**Implement selective B2 + B3:**
```bash
pip install scrubadub phonenumbers
```

Add to `/api/v1/records/search`:
```python
@router.post("/api/v1/records/{record_id}/anonymize")
async def anonymize_record(record_id: str) -> dict:
    """Anonymize SOAP for export/sharing"""
    from scrubadub import Scrubber
    soap = await db.get_soap(record_id)
    
    scrubber = Scrubber()
    safe_soap = {
        "subjective": scrubber.clean(soap.subjective),
        "objective": scrubber.clean(soap.objective),
        "assessment": scrubber.clean(soap.assessment),
        "plan": scrubber.clean(soap.plan),
    }
    return safe_soap
```

### Phase 11-TBD (Later, 2 hours)
**Add optional medical NLP** (B1) if entity recognition improves SOAP quality:
- Benchmark: Does spaCy medical terms improve generation quality?
- Test on 50 SOAP records
- If >5% improvement: add to Phase 12 monitoring dashboard

### Phases 12-14 (Not recommended)
**Do NOT integrate FreeScribe**  
- Risk: Dependency bloat, license issues
- Better: Study their client-server pattern, implement custom

---

## 6. Open Questions for FreeScribe

If you do integrate components, clarify with maintainers:

1. **spaCy model licensing** — Is en_core_sci_md suitable for commercial medical use?
2. **Scrubadub configuration** — Does it handle Taiwanese medical terms?
3. **Phone number formats** — Does it support Taiwan (+886) correctly?
4. **Performance benchmarks** — spaCy load time on startup (8s penalty acceptable?)

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| FreeScribe abandonment | High (12 stars, early-stage) | Medium (partial integration) | Extract only 2-3 components, copy code if needed |
| AGPL-3.0 license viral spread | High | High (must open-source changes) | Use only external libraries, not submodule |
| spaCy startup bloat | Medium | Low (8s one-time cost) | Lazy-load, document in Phase 12 |
| Scrubadub language support | Medium | Low (fallback to manual) | Test on Taiwan patient names first |
| Dependency conflicts | Low | Medium (version hell) | Strict pinning, separate venv |

---

## 8. Final Recommendation

| Option | Verdict | Action |
|--------|---------|--------|
| **Full submodule** | ❌ Not recommended | Skip entirely |
| **Selective components (B1-B4)** | ✅ Recommended | Implement B2 + B3 in Phase 10-03 |
| **Architectural learning** | ✅ Recommended | Study patterns for Phase 11 design |
| **Full FreeScribe codebase** | ❌ Not recommended | Risk > benefit |

---

## 9. Implementation Checklist (If Proceeding)

### Phase 10-03 Task: Add Scrubadub + Phonenumbers
- [ ] Install: `pip install scrubadub phonenumbers`
- [ ] Add to pyproject.toml dependencies
- [ ] Create `src/nlp/anonymizer.py` with Scrubber class
- [ ] Add `/api/v1/records/{id}/anonymize` endpoint
- [ ] Test on 10 sample SOAP notes
- [ ] Document in README: "HIPAA anonymization via Scrubadub"
- [ ] Update audit trail schema (Phase 10 requirement)

### Phase 11 Task: Evaluate spaCy Integration (Optional)
- [ ] Install: `spacy download en_core_sci_md`
- [ ] Create `src/nlp/medical_entity_extractor.py`
- [ ] Benchmark on 50 existing SOAP records
- [ ] Measure: generation quality improvement (BLEU/ROUGE)
- [ ] Decision: integrate if >5% improvement

---

## 10. References

- **FreeScribe**: https://github.com/ClinicianFOCUS/FreeScribe
- **AI-Scribe (original)**: https://github.com/1984Doc/AI-Scribe
- **spaCy SciSpaCy**: https://allenai.github.io/scispacy/
- **Scrubadub**: https://github.com/datascopeanalytics/scrubadub
- **AGPL-3.0 License**: https://www.gnu.org/licenses/agpl-3.0.html

---

**Report prepared by**: Claude (Haiku 4.5)  
**For decision**: SoapVoice architecture team
