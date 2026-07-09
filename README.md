# Openfill 규칙

원본 `sfinder.jar`는 수정하지 않고, 추가 규칙 파일만 붙여서 실행합니다.

이 규칙은 `--fill` 미노가 높이 떠 있어도, 다른 미노를 먼저 쌓아서 받친 뒤 채우는 해법을 허용합니다.

## 사용법

기존 명령의 앞부분만 바꾸면 됩니다.

```bat
sfinder-openfill.bat setup --tetfu v115@zgTpwhBeWpCeWpAewhXpBeXpBeTpJeAgH --patterns *p7 --fill i --margin o
```

`starter`에서 더블클릭하려면:

```bat
starter\run-setup-openfill.bat
```

## 배포할 파일

- `sfinder.jar`
- `sfinder-openfill.bat`
- `openfill-rule\sfinder-openfill-rule.jar`
- `starter\run-setup-openfill.bat`
