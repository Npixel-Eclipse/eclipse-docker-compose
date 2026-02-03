# n8n 공식 이미지를 기반으로 시작 (Alpine Linux 기반)
FROM docker.n8n.io/n8nio/n8n

# 루트 사용자로 전환하여 패키지 설치
USER root

# wget 설치
RUN apk add --no-cache wget

# Perforce CLI (p4) 다운로드 및 실행 권한 부여
RUN wget -qO /usr/local/bin/p4 https://cdist2.perforce.com/perforce/r24.1/bin.linux26x86_64/p4 \
    && chmod +x /usr/local/bin/p4

# p4_tickets 디렉토리 생성 및 권한 설정
RUN mkdir -p /home/node/p4_tickets \
    && chown -R node:node /home/node/p4_tickets

# Entrypoint 스크립트 추가
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 다시 node 사용자로 전환
USER node

# Entrypoint 설정
ENTRYPOINT ["/entrypoint.sh"]
CMD ["n8n", "start"]
