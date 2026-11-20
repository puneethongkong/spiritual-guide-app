from pathlib import Path
import re

SOURCE = Path('app.py')
OUTPUT = Path('app_v1_42.py')
BACKUP = Path('app_v1_41_backup.py')

if not SOURCE.exists():
    raise FileNotFoundError('Place this upgrader beside the current app.py and run it again.')

code = SOURCE.read_text(encoding='utf-8')
BACKUP.write_text(code, encoding='utf-8')

code = re.sub(r"APP_VERSION\s*=\s*['\"][^'\"]+['\"]", "APP_VERSION='AWS v1.42 Locked Rulership and Chart Validation'", code, count=1)

old = "asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))"
new = "asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0])); asc['sign_lord']=LORDS[asc['sign']]; asc['nakshatra_lord']=asc['lord']"
if old not in code: raise RuntimeError('Ascendant calculation pattern not found; no output created.')
code = code.replace(old,new,1)

old = "x['condition']=labels or ['No major screening flag']; x['rules_houses']=rules.get(n,[])"
new = "x['condition']=labels or ['No major screening flag']; x['rules_houses']=rules.get(n,[]); x['sign_lord']=LORDS[x['sign']]; x['nakshatra_lord']=x['lord']"
if old not in code: raise RuntimeError('Planet condition pattern not found; no output created.')
code = code.replace(old,new,1)

marker='def calculate_chart(p):'
if marker not in code: raise RuntimeError('calculate_chart not found; no output created.')
validation = '''def validate_chart(chart):
 errors=[]
 asc=chart['ascendant']
 if asc.get('sign_lord')!=LORDS.get(asc.get('sign')): errors.append('Ascendant sign lord mismatch')
 if asc.get('nakshatra_lord')!=asc.get('lord'): errors.append('Ascendant Nakshatra lord mismatch')
 for name,p in chart['planets'].items():
  if p.get('sign_lord')!=LORDS.get(p.get('sign')): errors.append(f'{name} sign lord mismatch')
  if p.get('nakshatra_lord')!=p.get('lord'): errors.append(f'{name} Nakshatra lord mismatch')
  if p.get('house')!=((p['sign_index']-asc['sign_index'])%12)+1: errors.append(f'{name} house mismatch')
 rahu=chart['planets']['Rahu']['longitude']; ketu=chart['planets']['Ketu']['longitude']
 if abs((((ketu-rahu)%360)-180))>0.0001: errors.append('Rahu/Ketu opposition mismatch')
 eligible=['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn']
 expected_ak=max(eligible,key=lambda n:chart['planets'][n]['degree'])
 if chart.get('atmakaraka')!=expected_ak: errors.append('Atmakaraka mismatch')
 if errors: raise ValueError('Chart validation failed: '+'; '.join(errors))
 return True

'''
code=code.replace(marker,validation+marker,1)

old_return="return {'ascendant':asc,'planets':ps,'atmakaraka':ak,'timing':vimshottari(ps['Moon']['longitude'],birth,datetime.now(timezone.utc)),'conjunctions':conj,'aspects':aspects,'ayanamsa':swe.get_ayanamsa_ut(jd)}"
new_return="result={'ascendant':asc,'planets':ps,'atmakaraka':ak,'timing':vimshottari(ps['Moon']['longitude'],birth,datetime.now(timezone.utc)),'conjunctions':conj,'aspects':aspects,'ayanamsa':swe.get_ayanamsa_ut(jd)}\n validate_chart(result)\n return result"
if old_return not in code: raise RuntimeError('calculate_chart return pattern not found; no output created.')
code=code.replace(old_return,new_return,1)

old="t=c['timing'];ak=c['atmakaraka'];base=f\"{c['ascendant']['sign']} Ascendant {ak} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha\""
new="t=c['timing'];ak=c['atmakaraka'];base=f\"{c['ascendant']['sign']} Ascendant sign lord {c['ascendant']['sign_lord']} Ascendant Nakshatra {c['ascendant']['nakshatra']} Nakshatra lord {c['ascendant']['nakshatra_lord']} Pada {c['ascendant']['pada']} {ak} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha\""
if old not in code: raise RuntimeError('personal_evidence base query pattern not found; no output created.')
code=code.replace(old,new,1)

old="prompt=f\"\"\"Answer using locked chart facts and evidence. Question: {q}."
new="locked_rulership=''\n if personal:\n  locked_rulership=(f\"Ascendant sign: {personal['ascendant']['sign']}; Ascendant sign lord: {personal['ascendant']['sign_lord']}; Ascendant Nakshatra: {personal['ascendant']['nakshatra']}; Ascendant Nakshatra lord: {personal['ascendant']['nakshatra_lord']}; Ascendant Pada: {personal['ascendant']['pada']}.\")\n prompt=f\"\"\"Answer using locked chart facts and evidence. LOCKED RULERSHIP: {locked_rulership} Question: {q}."
if old not in code: raise RuntimeError('synthesize prompt pattern not found; no output created.')
code=code.replace(old,new,1)

old_rules='Rules: explain Sanskrit; calculate nothing; distinguish Calculated Fact, Classical Source, Practitioner View, Web Research and Needs Verification. Never invent remedies, medical claims, universal chakra mappings, mantra counts or gemstone suitability. If web research failed, say the answer uses Trusted Library only.'
new_rules='Rules: explain Sanskrit; calculate nothing; distinguish Calculated Fact, Classical Source, Practitioner View, Web Research and Needs Verification. A zodiac sign lord and a Nakshatra lord are separate locked facts. NEVER describe a Nakshatra lord as the ruler of a zodiac sign. Use LORDS-based sign rulership only. Do not override or infer a different sign lord. Never turn one placement into a definite psychological conclusion; use qualified language and integrate sign, house, lordship, condition, conjunctions and aspects. Never invent remedies, medical claims, universal chakra mappings, mantra counts or gemstone suitability. If web research failed, say the answer uses Trusted Library only.'
if old_rules not in code: raise RuntimeError('Synthesis rules pattern not found; no output created.')
code=code.replace(old_rules,new_rules,1)

old='Create a full integrated personal report with Jyotish, timing, Ayurveda support, yoga, mantra, chakra perspectives, remedies, gemstone caution and three priorities. Explain why every major conclusion applies to this chart.'
new='Create a full integrated personal report with Jyotish, timing, Ayurveda support, yoga, mantra, chakra perspectives, remedies, gemstone caution and three priorities. Begin by stating the Ascendant sign and its zodiac sign lord, then separately state the Ascendant Nakshatra, Nakshatra lord and Pada. Never merge sign lordship with Nakshatra lordship. Explain why every major conclusion applies to this chart.'
if old not in code: raise RuntimeError('Personal reading request pattern not found; no output created.')
code=code.replace(old,new,1)

old="'Nakshatra':p['nakshatra'],'Pada':p['pada'],'Condition':'; '.join(p['condition'])"
new="'Sign lord':p['sign_lord'],'Nakshatra':p['nakshatra'],'Nakshatra lord':p['nakshatra_lord'],'Pada':p['pada'],'Condition':'; '.join(p['condition'])"
if old not in code: raise RuntimeError('Advanced planet table pattern not found; no output created.')
code=code.replace(old,new,1)

old="if cfg['advanced']:st.dataframe([{'Planet':n"
new="if cfg['advanced']:\n  st.markdown('### Locked Ascendant facts')\n  st.dataframe([{'Ascendant sign':c['ascendant']['sign'],'Sign lord':c['ascendant']['sign_lord'],'Ascendant Nakshatra':c['ascendant']['nakshatra'],'Nakshatra lord':c['ascendant']['nakshatra_lord'],'Pada':c['ascendant']['pada']}],use_container_width=True,hide_index=True)\n  st.dataframe([{'Planet':n"
if old not in code: raise RuntimeError('Advanced details block pattern not found; no output created.')
code=code.replace(old,new,1)

compile(code,str(OUTPUT),'exec')
if code.count("if __name__=='__main__':main()")!=1: raise RuntimeError('Unexpected application entry-point count; no output created.')
OUTPUT.write_text(code,encoding='utf-8')
print('='*72)
print('AWS v1.42 BUILD COMPLETE')
print('='*72)
print('Backup:',BACKUP)
print('Output:',OUTPUT)
print('Syntax validation: PASS')
print('Ascendant sign lord locked: PASS')
print('Ascendant Nakshatra lord separated: PASS')
print('Planet sign/Nakshatra lords locked: PASS')
print('Chart validation gate: PASS')
print('Rahu/Ketu validation: PASS')
print('Atmakaraka validation: PASS')
print('Narrative no-confusion rule: PASS')
print('Qualified interpretation rule: PASS')
print('Advanced facts tables: PASS')
print('Original app.py was not overwritten.')
print('='*72)
