# 금칙어 시스템 Proto 변경사항

## 변경일: 2025-12-21

금칙어 시스템이 다중 서버에 적용되면서 각 서버의 Result Code가 추가되었습니다.

---

## 1. ClientLobbyResult.Code (lobby.proto)

**추가된 코드:**
```proto
CONTAINS_FORBIDDEN_WORD = 18;  // 금칙어 포함
```

**사용 상황:**
- 캐릭터 이름 생성 시 금칙어가 포함된 경우

**클라이언트 대응:**
- `CreateCharacterReply.result.code == CONTAINS_FORBIDDEN_WORD` 확인
- 시스템 메시지 출력: `UIWord_SystemMsg_IncludeForbiddenWord`
- "부적절한 언어가 포함되어 있습니다" 메시지 표시

---

## 2. GuildResultCode (guild.proto)

**추가된 코드:**
```proto
FAIL_CONTAINS_FORBIDDEN_WORD = 212;  // 금칙어 포함
```

**사용 상황:**
- 길드 이름에 금칙어가 포함된 경우 (길드 생성 시)

**클라이언트 대응:**
- 길드 생성 응답에서 `result == FAIL_CONTAINS_FORBIDDEN_WORD` 확인
- 시스템 메시지 출력: `UIWord_SystemMsg_IncludeForbiddenWord`
- "부적절한 언어가 포함되어 있습니다" 메시지 표시

**참고:**
- 길드 소개/공지는 **마스킹 처리**되므로 별도 에러 코드 없음
- 클라이언트는 마스킹된 텍스트를 그대로 표시

---

## 3. PkLogEvent.Result (pklog.proto)

**추가된 코드:**
```proto
FAIL_CONTAINS_FORBIDDEN_WORD = 10;  // PvP 메시지 금칙어 포함
```

**사용 상황:**
- PvP 승리/패배 메시지 설정 시 금칙어가 포함된 경우

**클라이언트 대응:**
- `SetPvpMessageResult.result == FAIL_CONTAINS_FORBIDDEN_WORD` 확인
- 시스템 메시지 출력: `UIWord_SystemMsg_IncludeForbiddenWord`
- "부적절한 언어가 포함되어 있습니다" 메시지 표시

---

## 4. MailResultCode (mail.proto)

**기존 코드 (변경 없음):**
```proto
FAIL_SEND_LETTER_BANNED_WORD = 15;
```

**참고:**
- 우편 제목/내용은 **마스킹 처리**되므로 이 에러 코드는 사용되지 않음
- 클라이언트는 마스킹된 텍스트를 그대로 표시

---

## 적용 범위 요약

| 기능 | 적용 대상 | 처리 방식 | Result Code |
|------|----------|----------|-------------|
| 캐릭터 생성 | 캐릭터 이름 | 거부 | `CONTAINS_FORBIDDEN_WORD (18)` |
| 길드 생성 | 길드 이름 | 거부 | `FAIL_CONTAINS_FORBIDDEN_WORD (212)` |
| 길드 생성/관리 | 길드 소개 | 마스킹 | - |
| 길드 관리 | 길드 공지 | 마스킹 | - |
| 우편 | 제목/내용 | 마스킹 | - |
| 기록실 | PvP 메시지 | 거부 | `FAIL_CONTAINS_FORBIDDEN_WORD (10)` |
| 채팅 | 채팅 내용 | 마스킹 | - |

---

## 클라이언트 구현 체크리스트

- [ ] Lobby: `CONTAINS_FORBIDDEN_WORD` 처리 추가
- [ ] Guild: `FAIL_CONTAINS_FORBIDDEN_WORD` 처리 추가
- [ ] PkLog: `FAIL_CONTAINS_FORBIDDEN_WORD` 처리 추가
- [ ] 시스템 메시지 `UIWord_SystemMsg_IncludeForbiddenWord` 정의 확인

---

**문의:** 서버팀
