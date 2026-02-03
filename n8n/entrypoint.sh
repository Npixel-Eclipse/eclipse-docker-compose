#!/bin/sh
# 루트로 실행하여 디렉토리 권한 수정
if [ "$(id -u)" = "0" ]; then
  chown -R node:node /home/node/p4_tickets 2>/dev/null || true
  # node 사용자로 스크립트 재실행
  exec su-exec node "$0" "$@"
fi

# 티켓 파일 확인
if [ ! -f "/home/node/p4_tickets/p4tickets.txt" ]; then
  echo "No Perforce ticket found, attempting login..."
  if [ -n "$P4PASSWD" ]; then
    echo "$P4PASSWD" | p4 login
    if [ $? -eq 0 ]; then
      echo "Perforce login successful, ticket saved to /home/node/p4_tickets/p4tickets.txt"
    else
      echo "Error: Perforce login failed with P4PASSWD"
      exit 1
    fi
  else
    echo "Error: P4PASSWD not set, cannot login automatically"
    exit 1
  fi
else
  echo "Perforce ticket found, checking validity..."
  p4 login -s >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "Ticket invalid or expired, attempting re-login..."
    if [ -n "$P4PASSWD" ]; then
      echo "$P4PASSWD" | p4 login
      if [ $? -eq 0 ]; then
        echo "Perforce re-login successful"
      else
        echo "Error: Perforce re-login failed"
        exit 1
      fi
    else
      echo "Error: P4PASSWD not set, cannot re-login"
      exit 1
    fi
  fi
fi

# n8n 실행
exec "$@"
