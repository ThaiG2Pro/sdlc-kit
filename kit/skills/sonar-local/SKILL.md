---
name: sonar-local
description: >
  Chạy SonarQube analysis ở local bằng npx sonarqube-scanner.
  Dùng khi muốn kiểm tra code quality trước khi push lên CI,
  hoặc debug tại sao Sonar CI check bị fail.
---

# Sonar Local Scan — {{PROJECT_TITLE}}

Chạy SonarQube scan ở local trỏ vào server `sonar-stg.gotit.vn`.

## Yêu cầu

- Node.js đang chạy (npx có sẵn)
- Coverage reports đã được generate (`coverage/lcov.info`)
- Có API token từ SonarQube server

## Lấy API token

1. Mở http://sonar-stg.gotit.vn
2. Vào **My Account → Security → Generate Token**
3. Copy token (chỉ hiển thị 1 lần)

## Bước 1: Generate coverage

```bash
npx vitest run --coverage
```

## Bước 2: Chạy scan

```bash
SONAR_TOKEN=<token> ./scripts/sonar-local.sh
```

Hoặc chỉ định project key khác:

```bash
SONAR_TOKEN=<token> SONAR_PROJECT_KEY=ten-repo ./scripts/sonar-local.sh
```

## Chạy thủ công (không dùng script)

```bash
npx sonarqube-scanner \
  -Dsonar.projectKey=<ten_repo> \
  -Dsonar.sources=. \
  -Dsonar.host.url=http://sonar-stg.gotit.vn \
  -Dsonar.login=<api_token_sonar>
```

## Đọc kết quả

Kết quả tại: `http://sonar-stg.gotit.vn/dashboard?id=<ten_repo>`

| Metric | Ngưỡng pass | Ý nghĩa |
|--------|------------|---------|
| Coverage | ≥ 80% | Tỷ lệ code được test |
| Bugs | 0 | Lỗi logic tiềm ẩn |
| Vulnerabilities | 0 | Lỗ hổng bảo mật |
| Duplications | < 3% | Code bị duplicate |
| Code Smells | Thấp | Code khó maintain |

## Troubleshooting

**Lỗi: Coverage not found**
- Chạy `npx vitest run --coverage` trước
- Kiểm tra `sonar-project.properties` có đúng path `coverage/lcov.info`

**Lỗi: Unauthorized**
- Token hết hạn hoặc sai → tạo token mới trên SonarQube UI

**Lỗi: Project not found**
- Kiểm tra `SONAR_PROJECT_KEY` khớp với project key trên server
