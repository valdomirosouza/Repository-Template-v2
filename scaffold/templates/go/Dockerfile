FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /service ./cmd/__SERVICE_NAME__

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /service /service
EXPOSE 8000
ENTRYPOINT ["/service"]
